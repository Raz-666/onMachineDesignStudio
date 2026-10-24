# R2-D2 Macro System — The User Manual

**Package:** `klipper-e3-r2d2` · Ender-3 + BTT SKR mini E3 + Pi Zero 2 W (Mainsail) ·
12864 LCD (16 characters per line)

This is the operating manual for the complete macro system: what the printer can
do, how every kind of file is printed, plotted or turned into labels and partial
prints, and how to tune a running job. It is organized the way you use the
machine — daily workflow first, generators next, calibration after that,
reference tables at the end. Installation and wiring live in the appendices.

**How to read this manual**

- **New to the system?** Read chapters 2–4. They walk you from uploading a file
  to a finished print — including every dialog you will meet.
- **Want to make labels, plot an image or print just a section of a file?**
  Chapter 5 covers all three generators with every parameter.
- **Print quality to improve?** Chapter 10 is the calibration ladder — in the
  order it should be done, matching the Maintenance menu on the LCD.
- **Looking for a specific menu, macro or console message?** Chapters 14–25 are
  the reference part; the cheat sheet (ch. 24) has the short paths.

## Table of contents

1. [Safety first](#1-safety-first)
2. [The system in five minutes](#2-the-system-in-five-minutes)
3. [From file to print — the daily workflow](#3-from-file-to-print--the-daily-workflow)
4. [Scenario library — every file type walked through](#4-scenario-library--every-file-type-walked-through)
5. [The generators: Range, Labels, Plotter, Cable ties, Angles, Lithophanes, ColorPic, Gaskets, Frames, Bricks, Kits & Figures](#5-the-generators-range-labels-plotter-cable-ties-angles-lithophanes-colorpic-gaskets-frames-bricks-kits--figures)
6. [During the print: tuning, pauses, objects](#6-during-the-print-tuning-pauses-objects)
7. [Filament: load / unload / change / runout / cold pull](#7-filament-load--unload--change--runout--cold-pull)
8. [Temperature system L1/L2](#8-temperature-system-l1l2)
9. [Speed, acceleration & machine limits](#9-speed-acceleration--machine-limits)
10. [Calibration — the ladder to good prints](#10-calibration--the-ladder-to-good-prints)
11. [Bed mesh & KAMP](#11-bed-mesh--kamp)
12. [Purge / prime line](#12-purge--prime-line)
13. [Maintenance & care](#13-maintenance--care)
14. [LCD menu reference](#14-lcd-menu-reference)
15. [Overrides reference](#15-overrides-reference)
16. [Sound reference](#16-sound-reference)
17. [LED reference](#17-led-reference)
18. [Console messages](#18-console-messages)
19. [System: Klipper & Pi](#19-system-klipper--pi)
20. [Variables & editing the .cfg files](#20-variables--editing-the-cfg-files)
21. [What happens when a macro executes](#21-what-happens-when-a-macro-executes)
22. [Troubleshooting](#22-troubleshooting)
23. [Limits & known behavior](#23-limits--known-behavior)
24. [Cheat sheet: LCD paths & Mainsail commands](#24-cheat-sheet-lcd-paths--mainsail-commands)
25. [Complete macro index](#25-complete-macro-index)
26. [Electronics & expansion — U2C + EBB42 + Relay V1.2](#26-electronics--expansion--u2c--ebb42--relay-v12)

Appendices: [A Installation](#appendix-a-installation-detailed) ·
[B Power & electrics](#appendix-b-power--electrics) ·
[C First start & updates](#appendix-c-first-start--updates) ·
[D Version history](#appendix-d-version-history)

---

## 1. Safety first

A 3D printer combines hot heaters, high currents and unattended hours. This system
adds software guardrails — software is never a substitute for hardware safety.

**Hardware safety you should have**

- **Smoke detector** in the printer room — printers are fire load, especially overnight.
- Fused mains side, PSU with protection circuitry, cables in good condition.
- Cable strain relief at the heatbed (the classic Ender-3 chafe point).
- Clean bed, free airflow around the electronics, nothing flammable stacked on top.
- Never print behind a locked door; do not leave the printer alone for days.

**What the macro system does for you**

- Heaters off at print end (`heaters_off_at_end`) + hotend fan cool-down (`cooldown_fan_time`, default 30 s).
- Pauses KEEP temperatures on purpose (you want to continue) — CANCEL_PRINT turns heaters off.
- SYS_SHUTDOWN: heaters/fans/LEDs off BEFORE the Pi goes down (two presses).
- After a Klipper error: alarm sound + red/white LED strobe, system goes idle.
- Runout pauses at the next layer boundary — detected BEFORE the print starves.
- EMERGENCY_STOP (System menu or console) halts everything immediately.

**Smoke / heat action plan**

```
EMERGENCY_STOP  ->  switch off at the MAINS  ->  if smoking:
extinguish with CO2/foam only - NEVER water on live electronics
```

NOT protected by macros: a stuck MOSFET, a blocked fan, a loose heater cartridge.
Inspect the printer regularly.

## 2. The system in five minutes

**One idea carries the whole system: every file gets intercepted before it
prints.** A small Python service watches the gcodes folder and enriches every
arriving file; the macro layer catches every print start and holds it until you
have decided how it should run. Between the two, the printer always knows what
a file contains — material, layers, features, speeds — and can take over any
parameter without re-slicing.

**The Python tools (tools/)**

| Tool | What it does | When it runs |
|---|---|---|
| `r2_postproc.py` | THE interceptor: watches the gcodes folder (systemd service, 1 s heartbeat). Tags every new G-code with `LAYER_MARK` layer markers, an `APPLY_TYPE` marker after every `;TYPE:` comment and a `_FILE_INFO` parameter block (material, layer height × count, line widths, flow ratio, PA, by-object, nozzle, wall loops, measured per-feature speeds and accels). Contains the generators (Range, Labels, calibration towers, bridging test, resonance plates) and the plot converters (PNG/JPEG/SVG/PDF/TXT → pen-plotter G-code). | continuously (service) |
| `make_label_fonts.py` | builds the label fonts (stroke skeletons) that are baked into `r2_postproc.py` — SMOOTH, MONO and the small-text fonts COND, NARROW, CAPS. | build time only (not needed on the Pi) |
| `macro_render_test.py` | the 900+ test battery the package is built against | after edits |
| `config_validator.py` | checks all cfg modules + save-variable keys | after edits |
| `r81_golden_check.py` | byte-level regression net for the postproc paths | after edits |

Files are never destroyed: tagging rewrites a file once when it arrives
(already-tagged files skip); generators and converters always write NEW files.

**The mode state machine.** The macro `_STATE` always knows the mode:
idle → waiting (start dialog) → starting → printing → paused → filament →
finished → idle. Nearly every macro checks it first — PAUSE in idle just
answers politely.

**The watcher (macro side, 1-second heartbeat)**

- catches prints started WITHOUT PRINT_START (legacy files) → activates
  overrides + live tuning, resets the layer state
- counts layers via Z when the file has no LAYER_MARK markers (and in AS LEGACY
  mode)
- switches L1→L2 temps/fan/speed at the tracked layer 2 — mirror of LAYER_MARK
- detects sequential object changes (Z falling edge)
- temperature tower band control
- self-heals stuck pause states, disarms expired cancels (60 s), finishes
  legacy prints properly

**Overrides instead of re-slicing**

```
Rule:     override ON + value > 0  =  applied. Otherwise the file rules.
Priority: LCD override (ON)  >  file value  >  material preset.
```

M104/M109/M140/M190/M106/M204/M220/M221/SET_PRESSURE_ADVANCE/SET_RETRACTION from
the file are intercepted and redirected — strictly by layer (ch. 8). The
interceptors remember what the FILE asked for — temps, PA, retraction, fan
value, flow factor (shown as `File H:215/210C` hints in the menus). This is why
you can print the SAME file in a different material without opening the slicer:
load another material preset (Pre-Print > Material) and start AS LEGACY.

**Universal print intercept.** SDCARD_PRINT_FILE (print button) and M24 (LCD
file list) catch EVERY print: the file is loaded and **held at position 0** —
not a single command runs before your decision. Then: homed if needed, start
dialog. The decision rides along until the file identifies itself; a net probe
(`_START_NET_PROBE`) catches files that neither heat nor call any start macro
and gives them home + heat + purge.

**Render before execute.** Klipper renders a whole macro template BEFORE
running it — a macro cannot see values it just set. Verification phases
therefore run as `delayed_gcode` seconds later (ch. 21). This one fact explains
most quirks:

| What you see | What it really is | What to do |
|---|---|---|
| a macro seems to "wait" for a state it just set | render-before-execute | nothing — by design |
| M104 logs "OVERWRITE" but the temp stays at the file value | print runs AS SLICED | switch mode or set the overwrite ON |
| "State re-synced" after an object change | watcher self-healing | cosmetic — ignore |
| LCD shows "File: …" next to your override | the interceptor captured the file value | compare on the spot |

## 3. From file to print — the daily workflow

This chapter is the complete path from "I have a file" to "the print is done",
with every click along the way. Later chapters go deeper; this one keeps you
moving.

### 3.1 Getting a file onto the printer

**Via Mainsail (recommended).** Drag the file into the gcode files panel (or
use Upload). Within a second of arriving, the postproc service has read and
tagged it: `; R2-POSTPROC v4` at the top, a `_FILE_INFO` parameter block after
the first command line, `LAYER_MARK` before every layer and `APPLY_TYPE` after
every `;TYPE:` comment. The console logs one line per file, e.g.
`[ok] vase.gcode: +312 LAYER_MARK (layer comments), +58 APPLY_TYPE, _FILE_INFO (layers=312, by_object=False)`.

**Via USB / scp / download.** Same thing — anything that lands in the gcodes
folder is processed, foreign downloads included. Files already carrying the
tag are skipped (nothing is double-processed).

**Selecting on the LCD.** The printer's file list (M24 path) opens the start
dialog before anything moves (see 3.5). At the moment you SELECT a file, its
`_FILE_INFO` is replayed to the system: Pre-Print > File info + Live Tuning > File (G-code) immediately
shows THAT file's values — material, layers, speeds, features — never
leftovers from the previous print.

**What the selection preview tells you** (Pre-Print > File info, same data as the
Live Tuning > File (G-code) panel):

| Field | Meaning |
|---|---|
| Type | MARKED (fully tagged) / LEGACY (no markers) / PLOT (pen file) |
| Sliced by | R84: the slicer + version and the firmware flavor the file was made for (OrcaSlicer, PrusaSlicer, Cura, Elegoo, Kiri:Moto, AstroPrint, SliceBeam, … for Klipper / Marlin) — works for fresh uploads AND foreign downloads |
| Material, layer height × count, line width, flow ratio | straight from the slicer header |
| By-object | sequential printing detected (several objects, Z falls) |

**Preheat on select (R62, 182 °C since R106):** the moment a file is
selected the nozzle preheats to **182 °C** and the bed to 60 °C — the
nozzle value is the **filament-swap level**: hot enough to change filament
(the extruder needs ≥180 °C) while the start dialog still asks AS SLICED /
AS LEGACY, still below serious ooze. Editable: Pre-Print > Preheat; OFF
there → nothing heats. The start sequence only heats the last few degrees.
| TYPES= | which features the file really contains (walls, infill, supports …) |

**Two file quirks the system flags and FIXES for you — in place, no
re-upload (R84/R85):**

- **Marlin-volumetric files** (`;FLAVOR:Marlin (Volumetric)`, e.g. from Cura):
  they count E in mm³ — Klipper expects mm and would print them heavily
  under-extruded. The file info shows the warning and the print start says it
  out loud (alarm + M117). **Pre-Print > File info > `Vol->mm fix`** converts the
  file directly: every E value (including G92) is divided by the filament
  cross-section (1.75 mm → 2.405 mm²), the volumetric markers are neutralized
  and a conversion note lands in the header. R2-D2 beeps at the start and
  plays the happy tune when the file is Klipper-ready (then simply select it
  anew). Idempotent — a converted file is never converted twice.
- **Old Bowden-era files** with long baked-in retracts (5–6 mm where your
  direct extruder wants ~0.8): select the file, then **Pre-Print > File info >
  `RetFix file`** — the watcher rewrites the file ON DISK: clean
  retract/unretract pairs become **G10/G11** (firmware retraction), so your
  CURRENT retraction applies — live-tunable during the print. The R2 markers
  survive (no re-processing needed), wipes and folded retracts stay
  untouched, start beep + done beep, and the console reports the pair count.
  If a start dialog holds the file it is released automatically first. For
  future uploads you can instead leave **Pre-Print > File info > RetFix ON** — every new
  upload gets the treatment automatically.
- **The offer only shows when it applies:** files that use **firmware
  retraction (G10/G11)** — e.g. OrcaSlicer with firmware retraction enabled —
  and files whose retracts are **already fixed** never show `RetFix file`
  again. The file info says which case you have: `retract … (firmware
  G10/G11)` / `(FIXED -> G10/G11)` / `(slicer moves — Pre-Print > File info:
  RetFix!)` / nothing detected = offer stays hidden (field log .72).

| FS_* / FA_* | the MEASURED original speed / acceleration of each feature |
| L1/L2 temps, PA, retraction, fan, nozzle, wall loops | everything Pre-Print can override |

**Click pacing (R85):** actions that write many values at once (material
select, preset load/save, range create, file fixes, the part generators)
insert ~100 ms micro-pauses between the disk writes — the Pi Zero never faces
a write burst. While a print runs the pauses no-op (a dwell would stutter
motion).

### 3.2 What the tools do with every file — the flow

```
upload / copy / scp ──►  gcodes folder
                              │  r2_postproc.py (service, 1 s)
                              ├─ G-code ──► tagged in place: LAYER_MARK,
                              │             APPLY_TYPE, _FILE_INFO, TYPES/FS/FA
                              ├─ photo.png / .jpg / .svg / .pdf / .txt
                              │        ──► untouched: select it in the file
                              │            list → Vnn_Plot_* generated on demand
                              └─ generated later on demand (Vnn_ leads =
                                  top of the list + your version number):
                                  Range Vnn_<src>_L<a>-<b>.gcode
                                  Label Vnn_<text>.gcode
                                  TempTower / RetractTower / FlowCube /
                                  Bridge / Resonance plates
                              ▼
        you press PRINT ──► file held at position 0 ──► start dialog
                              ▼
        AS LEGACY (takeover) or AS SLICED (file 1:1)
                              ▼
        homing → bed temp → adaptive mesh → hotend → nozzle wipe → purge line
                              ▼
        layer 1: L1 temps, fan off, speed brake ──► layer 2: L2 temps,
        file fan back, 100% speed ──► … print … ──► PRINT_END: park,
        stats, fanfare, cooldown, heaters off
```

Everything in this flow is live tunable and pausable (ch. 6), every object is
skippable, and the print can be ended normally at any planned layer (ch. 6.5).

### 3.3 G-code file types and how the system tells them apart

The system classifies every file — this decides what the start dialog offers
and which automatic rules apply:

| File type | How it is detected | What the system does |
|---|---|---|
| **Print by layer** (normal) | layer comments (`;LAYER_CHANGE`, `;LAYER:n`, `;CHANGE_LAYER`) or Z-scan; `BY_OBJECT=0` | the normal case: L1 rules on layer 1, L2 switch at layer 2, feature overrides per `APPLY_TYPE` |
| **Print by object** (sequential) | several objects + Z falling edges (`BY_OBJECT=1`), or falling `;Z:` comments | at every object change: L1 temps + L1 speed again (pause only if a heater must actually move), next object's layer 2 switches back to L2 — the layer counter re-anchors at every object start |
| **Multi-object with object data** | `EXCLUDE_OBJECT_DEFINE` lines in the file | adaptive KAMP mesh over the real objects, per-object skip (ch. 6.5), smart parking away from the remaining objects |
| **Vase mode** (continuous Z) | Z-scan: slow continuous rise < 0.05 mm per move | layer marks accumulate until 0.18 mm — vase prints still get layer events; spiral files run like any other |
| **Legacy file** (old slicer profile, foreign download, no markers) | no `; R2-POSTPROC` tag, no PRINT_START | watcher catches the start → LEGACY start dialog; AS LEGACY = full takeover (mesh, purge, L1/L2, Z layer counting) |
| **Old mod file** (calls its own START_PRINT) | `START_PRINT` in the file | real legacy start: homing, heat, purge — then your decision rules |
| **Pure movement data** (no heaters, no start macro) | net probe: nothing heats, nothing calls | home + heat + purge before the file runs 1:1 |
| **Plot file** (pen) | `; R2-PLOT` header | plotter flow: no purge with a pen, AS LEGACY heats only when the extruder is ON; live tuning works while plotting |
| **Generated file** (Range / Labels / towers / plates) | carries the tag + PRINT_START header | runs through the NORMAL start flow like any sliced file |

**Layer detection without comments:** files without layer comments get a
Z-scan — a Z rise between 0.05 and 0.35 mm on an extruding move is a layer
boundary; a slow continuous rise is treated as vase mode. You see the method in
the console (`(Z scan)` vs `(layer comments)`).

### 3.4 Pre-Print — the settings before you start

Pre-Print is the panel you visit while the printer heats or before you commit.
Everything here is saved and reused; nothing is lost on restart.

| Entry | Contents |
|---|---|
| Offset X/Y/Z (.104) | SET_GCODE_OFFSET for X/Y/Z at the very top: ±0.1 mm steps + fine rows with ±0.05 mm (halved steps for the last bit of baby-sitting), applied live (MOVE=1) |
| File (G-code) | full slicer summary of the SELECTED file (type, material, layers, speeds, accels, temps, PA, retraction) + 16 feature activator rows: each shows the file's real speed and an ON switch — features the file does not contain show 'n/a' and refuse · Flow line: MAXRATE mm³/s (+ seam position, + *derived* marker when the geometry classifier tagged this file) · Cap / Fix flow cap + TAcc / Fix travel accel (.85) |
| Material | LOAD NOW + all material values (Bed/Hotend L1/L2, PA + smooth, flow, retract, fan L2) + Save as preset — edits of the ACTIVE material apply live |
| Temperatures | Bed/Hotend L1/L2 + Fan L2 (ON/OFF each) + the file's own values for comparison |
| Velocity (.104) | retraction length/speed/unretract + File R: display, acceleration, velocity, minimum cruise ratio, square corner (ON/OFF each) + Z-Hop ON/OFF + height — the global PA moved to PA per feat. (.107) **Drive** at the top of Retraction: DIRECT/BOWDEN starting-point profile (SET_EXTRUDER_DRIVE) — sets sane values, everything stays freely editable; ranges span both worlds (length 0–15 mm, speeds 5–100 mm/s) |
| Spd/Acc/PA/Flw per feat (.104) | four quick lists (also in Live Tuning): per-feature speed / accel / PA / flow, each led by its GLOBAL — 1st-layer speed (Spd), global accel + ON (Acc), global PA + smooth + File PA (PA), global flow + ON (Flw) — plus Now: the feature currently printing. The old top-level Speeds/Accels/Flow menus were merged here |
| Features | 16 submenus, one per feature (outer/inner wall, overhang wall, sparse/solid infill, top/bottom surface, bridge, internal bridge, gap fill, support, ironing, skirt, brim, prime tower, custom code): file original + ON switch + speed % + accel + PA each (.85) |
| Bed Mesh | Level old files · Mesh ON/AUTO/OFF · Save after · Adaptive · Travel cap while meshing · Calibrate now · Load…/Delete… |
| Profiles | per-file profiles (pre/post) + default profiles + material presets — see 3.4a (.84) |
| Range/Stop | planned end at layer N + the range generator with floor/top holes (ch. 5.1) |
| Filament | Load / Unload / Change (M600) before the print, load & unload lengths |
| Plotter (.104) | only for plot files: PEN FILE picker, pen speed %, Pen Z, Shift X/Y, Reset overrides — at the very END of Pre-Print |

**The golden rule:** overrides only apply when they are ON. A stored value
without ON never touches the print; the file rules until you switch something
on.

### 3.4a Per-file profiles — the memory of every print (.84)

Every legacy-printed file can carry its OWN profile: all pre-print settings
(temps L1/L2, PA + smooth, retraction, motion, flow, fan, ironing flow,
first-layer speed, material, all 16 feature switches with their speed/accel
values) plus everything you tuned LIVE during the print. Two slots per file:

| Slot | Written | Read |
|---|---|---|
| **pre** | MANUALLY: Pre-Print > Profiles > This file > Save as pre | Load button — and at every file selection when Auto-load is ON |
| **post** | (.128) LEGACY: entries written by versions before .128 — load or delete them manually, nothing is ever written here anymore (the automatic after-print takeover became the **Rate print?** question, §3.7a) | Load / Delete button |

Rules of the game:

- (.128) **Auto-load applies YOUR `pre`** when one exists — a legacy `post`
  slot never auto-applies (it stays manually loadable).
- Cancelled prints write nothing.
- The key is the file path below the gcodes root, so `Petg/vase.gcode` and
  `vase.gcode` are two different files — exactly like the selection list.
- Pre-Print settings beat material presets: applying a profile writes the
  values AND their ON switches (the old "load default preset never switched
  anything on" bug is fixed with the same code path).

**Pre-Print > Profiles** has three sub-menus:

| Sub-menu | Contents |
|---|---|
| Material | LOAD / SAVE / RESET for PLA, PETG, TPU (save writes the material values WITHOUT loading anything first) + LOAD/SAVE for ABS/ASA — the same presets as Pre-Print > Material |
| Defaults | the 8 standalone default profiles: Save (current state) · Info (list all) · Load 1–8 · Delete 1–8 |
| This file | Save as pre / Load pre / Load post / Delete pre / Delete post + Auto-load ON/OFF — load/delete items appear only when that slot exists |
| From optimized | (.128) the tuned library in `gcodes/optimized/`: pick a number and click — its values become the Pre-Print **starting point** for the next print (nothing is written to any file). Plus **Save last print > optimized**: the second chance if the Rate print? question was missed (idle only) |

`SAVE_MATERIAL_TEMPS`/`SAVE_DEFAULT_PRESET`/`SAVE_FILE_PROFILE` console
commands do the same as their menu items; `FILE_PROFILES_INFO` lists what is
stored for the selected file.

### 3.5 The start dialog — AS LEGACY or AS SLICED

Every print start (print button, LCD list, PRINT_START) stops at the dialog:

| Mode | LCD / console | What rules |
|---|---|---|
| **AS SLICED** | > PRINT AS SLICED · `PRINT_AS_SLICED` | the FILE, truly 1:1 — no overrides, no first-layer brake beyond the L1/L2 rules, no sequential restarts. Live commands still apply. The first-layer rules shape **layer 1** (material L1 temps, fan off); **from layer 2 the file runs 1:1** — its own M104/M140 stand, only YOUR armed L2 override still wins (.121). Toggle the rules with Pre-Print > Temperatures > L1 rules |
| **AS LEGACY** | > PRINT AS LEGACY · `PRINT_AS_LEGACY` | takeover with YOUR parameters: overrides ON (L1/L2 temps, PA, retraction, machine limits, flow), mesh + purge, Z layer tracking, sequential object handling |
| CANCEL | > CANCEL | aborts cleanly — nothing was heated |

**How to decide**

- Sliced with THIS system's profile, values as you want them → either mode
  works; AS SLICED is the honest 1:1 run.
- Foreign file, old profile, or you want your material preset / feature
  speeds / first-layer brake to apply → **AS LEGACY** (recommended default).
- Range and label files: the header comment in the file says it —
  AS LEGACY = your settings, AS SLICED = the source temperatures 1:1.

With `start_confirm` OFF, PRINT_START runs immediately as LEGACY takeover. The
dialog title shows the file type at a glance: `Start? MARKED` / `Start? LEGACY`.

### 3.6 While it prints

Everything is adjustable while the job runs — speed, flow, PA, accel, per-
feature speeds, temperatures, Z offset (babystepping), plus pauses, object
skips and the planned end. Chapter 6 is the complete reference; the short
version:

- **Live Tuning > Spd per feat** — global % and the CURRENT feature's % (the
  display names the feature that is printing right now); the four quick lists
  Spd/Acc/PA/Flw per feat carry the globals and the active feature at the top
- **Live Tuning > Extrusion** — flow, PA, retraction — every input shows what
  Klipper really runs at this moment
- **Live Tuning > Pause & Control** — pause now / next layer / at layer N /
  planned end at layer N / M600 change / cancel (2×)
- **Live Tuning > Objects** — skip a single object

### 3.7 After the print

PRINT_END (or a planned end, or the end of a legacy file) runs the full
choreography: lift, park away from the part, stats on the console, fanfare,
cooldown with the part fan, heaters off. The LED celebration runs for
`led_finish_time` seconds and returns to idle by itself. `_PRINT_CLEANUP`
resets all per-print state — the next print starts clean, with your pre-print
settings, the selected material and the loaded mesh deliberately KEPT.

If — and only if — the print was successful AND you tuned something live, the
**Rate print?** question appears at the top of the menu (§3.7a).

### 3.7a Rate print? — optimized copies (.128)

Live tuning during a print used to be silently taken over into Pre-Print (and
into an automatic `post` profile). Since .128 it is a decision:

| Answer | What happens |
|---|---|
| **YES — optimized copy** | the tuning STAYS and the watcher writes an **optimized copy** (below). Confirm sound, `Optimized: saved` on the display. |
| **NO — discard** | the exact **pre-print baseline** (snapshotted at the print start, memory only) is restored — every override, feature switch, clamp and material — the tuning is gone without a trace. |
| **90 s of silence** | counts as NO. Starting the next print or selecting another file also resolves it immediately — an unanswered question never blocks anything and never leaks into the next print. |

The **optimized copy** lands in `gcodes/optimized/` under the SAME file name —
the original file is only ever **read** (byte-identical, provable by md5/diff).
The copy carries your print's tuning:

- Values the file can display are **baked in as absolutes**: flow and speed
  percents (flow, per-feature speed, global M220 speed) are scaled into the
  file's own values, PA / accel / first-layer speed / fan limits are written
  directly. Pre-Print > File info shows the OPTIMIZED row instead of raw
  slicer values.
- Percent values are **neutralized in the replay** — reprinting the copy can
  never apply them a second time. Absolute values stay in the replay too
  (applying them twice is a no-op).
- Everything without a display key (temps, retraction, per-feature flow/PA)
  rides in the `_OPT_BAKED` replay line — the copy prints with exactly the
  values the successful print ended with, even from a cold start.
- The header notes source file + date (`; R2-OPT`) and what was baked.
- Re-optimizing the same source overwrites its copy — the newest round wins.

**Printing a copy:** the stock LCD file list shows the gcodes root ONLY
(Klipper never lists subfolders there), so the top-level **Optimized** menu is
the LCD way in: pick a number, **START** (the start dialog asks as always) or
**Values > Pre-Print**. Mainsail/Fluidd show the folder natively. Selecting a
copy marks it OPTIMIZED everywhere.

**Taking values without printing:** Pre-Print > Profiles > **From optimized**
(see §3.4a) — the second chance **Save last print > optimized** sits in the
same menu.

### 3.8 Foreign G-code — other slicers, other firmware, other hardware

Files not sliced by you, not sliced for Klipper, or sliced for a DIFFERENT
extruder: here is the complete map of what differs, what the system handles
by itself, and where you click once.

**A) Other slicers — detected, normalized, zero clicks**

The watcher recognizes 12 slicer families by their header signature (OrcaSlicer,
PrusaSlicer, SuperSlicer, Bambu Studio, Cura, Elegoo Slicer, Kiri:Moto,
AstroPrint, SliceBeam, ideaMaker, Simplify3D, FlashPrint) and normalizes
their dialects:

| What differs between slicers | What the system does |
|---|---|
| layer comments: `;LAYER_CHANGE` (Orca/Prusa) · `;LAYER:n` · `;CHANGE_LAYER` (older/other) | all recognized — a `LAYER_MARK` is inserted for each; files with NO layer comments get a Z-scan instead (and say so in the console) |
| feature names: Orca `;TYPE:Outer wall` · Cura `;TYPE:WALL-OUTER` · `;TYPE:Support/Base` … | everything is mapped to the system's 16 internal feature codes — overrides work on ANY slicer's file (full census table below) |
| config headers `; line_width = 0.62` … | the relevant keys are read into `_FILE_INFO` (line widths, flow ratio, PA, speeds) — the Pre-Print preview shows the file's REAL values |
| `EXCLUDE_OBJECT_DEFINE` blocks | only present when the slicer was told to label objects (Orca: "Label objects") — with them: adaptive mesh + live skip; without: honest full-bed mesh message |

**A.1) The feature census — all 16 features in every slicer family** *(R95)*

Every modern slicer writes `;TYPE:` comments into the G-code. The
post-processor maps each spelling (lowercase, dashes/spaces equal) to one
internal code, measures the speeds/accels per feature and injects an
`APPLY_TYPE` marker after every `;TYPE:` — that is what makes features live
tunable. Values with NO own marker (e.g. small perimeters) come from the
config header (`; key = value` lines) into the file info instead.

| System feature (menu) | OrcaSlicer / Bambu Studio | PrusaSlicer / SuperSlicer | Ultimaker Cura | How it reaches the system |
|---|---|---|---|---|
| OW Outer wall | `Outer wall` | `External perimeter` | `WALL-OUTER` | `;TYPE:` marker |
| IW Inner wall | `Inner wall` | `Perimeter` (`Thin wall` → here) | `WALL-INNER` | `;TYPE:` marker |
| OH Overhang wall | `Overhang perimeter` | `Overhang perimeter` | — (stays in WALL-OUTER) | `;TYPE:` marker |
| SP Sparse infill | `Sparse infill` | `Internal infill` | `FILL` | `;TYPE:` marker |
| SO Solid infill | `Internal solid infill` | `Solid infill` | — (in FILL/SKIN) | `;TYPE:` marker |
| TP Top surface | `Top surface`, `Top solid infill` | `Top solid infill` | `SKIN` | `;TYPE:` marker |
| BT Bottom surface | `Bottom surface`, `Bottom solid infill` | `Bottom solid infill` | `SKIN` (bottom) | `;TYPE:` marker |
| BR Bridge | `Bridge` | `Bridge infill` | `BRIDGE` | `;TYPE:` marker |
| IB Internal bridge | `Internal bridge` | `Internal bridge infill` | — | `;TYPE:` marker |
| GP Gap fill | `Gap fill`, `Gap infill` | `Gap fill` | — | `;TYPE:` marker |
| SU Support | `Support`, `Support interface`, `Support transition` | `Support material` (+ interface) | `SUPPORT`, `SUPPORT-INTERFACE` | `;TYPE:` marker |
| IR Ironing | `Ironing` | `Ironing` | — | `;TYPE:` marker |
| SK Skirt | `Skirt`, `Ooze shield` | `Skirt` | `SKIRT` | `;TYPE:` marker |
| BM Brim | `Brim` | `Brim` | `BRIM` | `;TYPE:` marker |
| PT Prime tower | `Prime tower` | `Wipe tower` | `PRIME-TOWER` | `;TYPE:` marker |
| CU Custom code | `custom` (custom G-code sections) | `custom` | — | `;TYPE:` marker |

**Speed-only — visible in the file info, not live-tunable:**

| Value | Slicer setting | Note |
|---|---|---|
| Small perimeters | `small_perimeter_speed` / `small_perimeter_acceleration` (Orca/Prusa; Orca default 50 % of the wall speed) | a pure SPEED setting — the slicer decides per loop which wall counts as 'small', there is no own `;TYPE:` marker. Speeds/Accels in the file info show Speed (small)/Accel (small) so you can see why short loops run slower. |

**Mapping decisions for types without an own menu entry** (documented in
`r2_postproc.py` `TYPE_MAP`): `Thin wall` → IW, `Skin` → TP (bottom-skin →
BT), `Raft` → BT, `Support interface`/`transition` → SU, `Ooze shield` → SK,
plain `Infill` → SP.

**The mystery low-accel feature from the field log** — a feature switch with
low acceleration values that no menu owned: those were **custom G-code
sections** (per-object start/end, filament-change, layer-change G-code with
their own `M204`). They now arrive as **CU Custom code** and are editable
like any other feature — including an accel limit that keeps their own M204
in check.

**A.2) The geometry classifier — feature control for files WITHOUT `;TYPE:` tags** *(.85)*

ideaMaker, old Simplify3D profiles or hand-written G-code carry no `;TYPE:`
comments at all — no feature marker, no live tuning. For those files (and
ONLY those) the post-processor now **derives the features from the geometry
itself**: closed loops with nesting → outer/inner walls, parallel straight
lines with regular spacing → sparse or solid infill (spacing ≥ 3 mm = sparse),
solid fill on layer 1 → bottom surface, solid fill on the last layer → top
surface. Z-changes on travel moves count too (modal-Z: Z-hops never fake a
layer change).

**The system stays honest about it:** the file info says `DERIVED=1 CONF=0.7
COVER=…%` — *detected, not assumed*. Curved open paths stay UNCLASSIFIED
(they simply print 1:1), bridges are never guessed (needs the layer below —
documented limit), and a file WITH tags is never classified: the first
`;TYPE:` wins, tagged data always beats the guess. Derived features carry
the fixed confidence 0.7 and the console line explains it in plain words.

**B) Files sliced for Marlin (other firmware) — two real differences**

Klipper-flavored files and Marlin-flavored files share nearly all commands,
but two Marlin habits break on Klipper. Both are detected, flagged loudly,
and fixed in place:

| Marlin habit | Symptom on Klipper | The fix |
|---|---|---|
| **Volumetric E** (`;FLAVOR:Marlin (Volumetric)`, common from Cura profiles with volumetric mode on) | E counts mm³ instead of mm → the print starves, barely extrudes at all | **Pre-Print > File info > `Vol->mm fix`**: every E value (G0/G1 and G92) is divided by the filament cross-section (1.75 mm → 2.405 mm²), the volumetric markers are neutralized, a note lands in the header. Idempotent — never converts twice. |
| **Long retraction moves** (E-only retract/unretract pairs, typical 5–6 mm from Bowden-era profiles) | they work, but they OVERRIDE your tuned ~0.8 mm direct-drive retraction and cannot be live-tuned | **Pre-Print > File info > `RetFix file`** **(or Pre-Print > File info > RetFix ON for every FUTURE upload)**: clean pairs become `G10/G11` firmware retraction — your current retraction applies and stays live-tunable. Wipes and folded retracts stay untouched. |

The file info line **"sliced by <slicer> for <firmware>"** (Pre-Print > File info)
tells you upfront what you are holding — fresh uploads and foreign downloads
alike. Marlin files WITHOUT volumetric markers and without extreme retracts
just run: the LEGACY start flow (dialog, mesh, purge, L1/L2) takes over.

**C) Files from other hardware (Bowden profile → your direct extruder)**

An old file from your Bowden days (or a friend's Bowden machine) contains
retraction distances tuned for a 400 mm filament path. Your direct extruder
wants ~0.8 mm. `RetFix file` rewrites exactly those pairs to G10/G11 — the
DISTANCE then comes from your saved retraction setting (Pre-Print > Velocity,
live-tunable during the print via Live Tuning > Extrusion). Nothing else in
the file changes; the R2 markers survive, so no re-processing happens.

The reverse (direct-drive file on a Bowden machine) is simply the same
setting tuned the other way — no file fix needed, just your retraction
values.

**D) Two more file fixes — hotend protection & travel accel** *(.85)*

The file info shows the **maximum volumetric flow** the file really uses
(`MAXRATE`, mm³/s — measured from F × E-per-mm, travels excluded). A hotend
does ~8–15 mm³/s; a file that asks for 25 silently skips and under-extrudes
on small nozzles.

| Fix | What it does | You click… |
|---|---|---|
| **Flow cap** | every extruding move over the cap gets its F lowered so the volumetric rate stays under it (travels and retracts untouched; marker `; R2-FLOWCAP:` in the header, idempotent — a higher cap later simply re-fixes) | Pre-Print > File info > `Cap:` (value) + `Fix flow cap` |
| **Travel accel** | travel blocks get their own `M204 S…` (saved/restored around each travel run, the file's print accels stay) — separate travel tuning WITHOUT touching your global accel | Pre-Print > File info > `TAcc:` (value) + `Fix travel accel` |

Both run through the same background watcher as RetFix/Vol — the console
confirms, the LCD shows "working", the file is fixed in place (no re-upload).

**The retract verdict (.86) — one line, no guessing:** Pre-Print > File info shows
`Ret:` with exactly one of four verdicts for the selected file:

| Ret: | Meaning | Your move |
|---|---|---|
| `FIX!` | explicit slicer retracts up to X mm (Bowden era) — they OVERRIDE your tuned direct-drive retraction and cannot be live-tuned | `RetFix file` (one click) |
| `can X.Xmm` | explicit slicer retracts, moderate length | `RetFix file` only if you WANT firmware retraction to rule them live |
| `fixed` | already rewritten to G10/G11 — your retraction rules | nothing |
| `fw` | the slicer itself uses G10/G11 | nothing |

Old v4-tagged files show `--` until retagged (see below) — the verdict line
also explains itself in the console when clicked.

**Decision table — what happens when**

| You have… | The system… | You click… |
|---|---|---|
| a normal Klipper file from any of the 13 slicers | tags it, previews it, offers the start dialog | PRINT |
| a file with NO `;TYPE:` tags at all | geometry classifier derives walls/infill/surfaces (marked DERIVED, 0.7 confidence) — live tuning works on it | PRINT |
| a file asking more flow than your hotend does | file info shows MAXRATE + a hint | `Fix flow cap` with a sane cap |
| a v4-tagged file (tagged before .86) | fully functional — but the info line predates MAXRATE/SEAM/CFG replay/retract verdict (file check lists it as STALE) | System > File check > `RETAG` (2×) — 20 files per run, `.r2bak` backup each, never during a print |
| a Marlin-flavor file, no volumetric, normal retracts | same — LEGACY flow (mesh, purge, L1/L2) | AS LEGACY |
| a Marlin-volumetric file | flags it loudly (file info + alarm at start) | `Vol->mm fix`, then PRINT |
| an old Bowden-era file | tags it; long retracts stay as-is until you say so | `RetFix file` (or Pre-Print > Fixes > RetFix ON for all future uploads) |
| a file calling its own `START_PRINT` | real legacy start: homing, heat, purge — then your rules | decision in the dialog |
| pure movement data (no heaters, no macros) | net probe catches it: home + heat + purge first | nothing — it just works |


### 3.9 Slicing for this system — the settings that unlock everything

Why does G-code written for other firmware or machines print here at all?
Because the system does not trust the file — it READS it: the post-processor
normalizes 12 slicer families' dialects into one language (layer comments →
`LAYER_MARK`, feature names → the 16 internal codes, header → file info), the
interceptors translate Marlin habits on the fly (M104/M106/M140/M109/M204/
M220/SET_RETRACTION/SET_PRESSURE_ADVANCE are OUR macros), and PRINT_START/
PRINT_END wrap every file in the same choreography. What the system cannot
translate it DETECTS and offers a fix for (volumetric E, Bowden-era retracts).

**What you get when you slice the RIGHT way — the full package:**

| Requirement | What it unlocks |
|---|---|
| `;TYPE:` feature comments (default in every modern slicer) | the 16 feature overrides + Live Tuning showing the feature printing RIGHT NOW + measured per-feature originals in the file info |
| layer comments (`;LAYER_CHANGE` / `;LAYER:` / `;CHANGE_LAYER`) | layer counting, L1/L2 temp system, fan-from-layer-2, pause-at-layer, Stop@, the Range generator |
| Klipper flavor, absolute or relative E (both fine) | clean values everywhere; Marlin-volumetric works but needs the Vol->mm fix first |
| start gcode calls `PRINT_START` with the file's values (templates below) | the full start choreography: dialog, mesh, purge, first-layer rules |
| end gcode calls `PRINT_END` | park, stats, fanfare, cooldown — never a parked hot nozzle |
| "label objects" / per-object G-code enabled | KAMP adaptive mesh, object skip (2× confirm), smart park |
| no M220/M221 spam from custom scripts | the clean-global system (Live Tuning > Velocity keeps the global honest) |

**Start/end g-code that fills everything in** (Orca / Prusa / SuperSlicer /
Bambu / Elegoo — same placeholders):

```text
PRINT_START MATERIAL=[filament_type] BED=[first_layer_bed_temperature]
HOTEND_FIRST=[first_layer_temperature] HOTEND_AFTER=[temperature]
LAYER_HEIGHT=[layer_height] TOTAL_LAYERS=[num_layers]
OUTER_WALL_SPEED=[outer_wall_speed] SUPPORT_SPEED=[support_speed]
IRONING_SPEED=[ironing_speed]
PRINT_END
```

Cura (same idea, Cura placeholders): `PRINT_START MATERIAL={material_type}
BED={material_bed_temperature_layer_0} HOTEND_FIRST={material_print_temperature_layer_0}
HOTEND_AFTER={material_print_temperature} LAYER_HEIGHT={layer_height}` …
`PRINT_END`. Kiri:Moto, AstroPrint, SliceBeam, ideaMaker, Simplify3D, FlashPrint:
put the same PRINT_START/PRINT_END calls in their start/end g-code boxes with
their own placeholder names — the step-by-step for Orca and Cura lives in
`slicer/ORCA.md` and `slicer/CURA.md`.

**The per-slicer checklist (all 12 families)**

| Slicer | Flavor | Watch out for |
|---|---|---|
| OrcaSlicer | Klipper | the reference — works out of the box; enable "label objects" |
| PrusaSlicer / SuperSlicer | Klipper | same as Orca (config at the file tail is parsed too) |
| Bambu Studio | Klipper | export WITHOUT the Bambu-specific header macros; keep "type" comments on |
| Elegoo Slicer | Klipper | Orca fork — behaves like Orca |
| Cura | Klipper or Marlin | use the CURA.md start gcode; if the file says "Marlin (Volumetric)", run the Vol->mm fix once |
| Kiri:Moto | Klipper | layer comments are on by default; check that `;TYPE:` lines exist |
| AstroPrint | — | start/end gcode boxes: PRINT_START/PRINT_END manually |
| SliceBeam | Klipper | Orca-relative; verify feature comments in the preview |
| ideaMaker | Marlin default | set G-code flavor to Klipper; older profiles bake in long retracts → RetFix file |
| Simplify3D | Marlin default | set flavor Klipper; add PRINT_END (its default end script is minimal) |
| FlashPrint | Marlin | slicer is detected as FlashForge/FlashPrint; expect LEGACY start flow |

**Limits — what NO translation can fix (honest list)**

- The machine is still this machine: a file sliced for a bigger bed, a Delta,
  or 15 mm/s² accelerations will run — but clamped to YOUR limits (that is a
  safety feature, not a bug).
- M-codes the firmware does not know stop the print (Klipper errors on
  unknown commands) — slicer scripts with exotic Marlin tool changes are the
  usual suspect; move that logic to macros.
- Filament-runout logic of other firmwares (M600 variants) is replaced by the
  system's own filament handling.
- Arcs (G2/G3) are supported; nothing to do.
- AS SLICED means 1:1: overrides OFF, first-layer rules shape layer 1 (per your
  switch), Live Tuning still works (live commands are not overrides). From
  layer 2 the file's own temperatures stand — your armed L2 override wins.

## 4. Scenario library — every file type walked through

Real situations, start to finish. Each scenario lists the clicks and what the
system does in the background.

**Scenario A — correctly sliced, print by layer (the normal case)**
Slice with the R2 profile (the post-processing script is optional — the service
tags the file anyway). Upload → select → start dialog → **AS LEGACY**.
Homing, bed temp, adaptive mesh, nozzle wipe, purge, then layer 1 with L1
temps, fan off and the first-layer brake; at layer 2: L2 temps (your override
if armed, else the file's value, else the material preset — .121), the file's
fan value, 100 % speed. Feature overrides (speed/accel per feature) work
because the file carries `APPLY_TYPE` markers.
*LCD:* Start Print? > AS LEGACY. *Console:* `PRINT_AS_LEGACY`.

**Scenario B — correctly sliced, print by object (sequential)**
Same start as A. At every object change (Z falling edge) the system pauses
briefly, sets L1 temps + L1 speed, waits only if a heater must actually move,
then continues; the next object's layer 2 switches back to L2. The layer
counter re-anchors at every object start — per-object layer rules stay exact.

**Scenario C — legacy file, print by layer (old profile, foreign download)**
The watcher detects the file without markers → pause + start dialog titled
`Start? LEGACY`. **AS LEGACY** = system takeover: homing → bed temp → mesh
("Old files" ON) → hotend to L1 temp → purge → L1 speed → gapless continue
(the pause position is restored after the purge — no park/return dance). The
Z tracker counts layers — layer 2 brings L2 temps + fan + 100 % (same ladder:
your override > file value > material preset, .121 — works in both start
modes). File M104/M220 are redirected layer-strictly. **AS SLICED** = the file
rules 1:1 — its own start gcode runs, nothing is injected (live tuning stays
available; your armed L2 override still wins from layer 2).

**Scenario D — legacy file, print by object**
C plus the sequential falling edge per object (choose AS LEGACY — AS SLICED
never injects object handling).

**Scenario E — sliced file, but started AS LEGACY**
System takeover on a correctly sliced file: overrides ON, Z counting, feature
markers still fire. Useful to print a well-sliced file with your current
material preset.

**Scenario F — same file, different material (no re-slicing)**
You have a PLA-sliced file and want it in PETG:
1. Pre-Print > Material > LOAD NOW the PETG preset (or edit the values — the
   active material edits apply live).
2. Check Temperatures: your L1/L2 temps are ON, the file's temps lose.
3. Start AS LEGACY. Temps, fan curve, PA, retraction and flow come from the
   preset; the geometry stays the file's.
Only the material-related parameters are taken over — speeds and accelerations
stay the file's unless you override them in Features.

**Scenario G — printing a RANGE (partial print)**
A 6-hour vase broke at layer 200 of 626? Make the section a real part:
1. Select the SOURCE file (its layer count appears in the menu).
2. Pre-Print > Range/Stop: From 125, To 225, Floor 5, Brim 4 (example).
3. > Create — a few seconds later `Vase_L125-225.gcode` exists AND selects
   itself (the source file's selection is replaced, nothing is deleted).
4. Start dialog → **AS LEGACY** → the excerpt prints on a generated raft with
   a brim, ends with a proper PRINT_END (park, stats, fanfare).
Details and all parameters: ch. 5.1.

**Scenario H — printing LABELS (name tags without a slicer)**
1. Tools > Labels > Text: pick line 1–3, position, rotate to the character, click —
   the text assembles live on the display.
2. Tools > Labels > Settings: size (default 50×15), font (SMOOTH / MONO / COND /
   NARROW / CAPS), hole side + diameter, stroke = letter line width.
3. Job > Add label — repeat for several DIFFERENT labels (queue shows n/24).
4. Job > Create (press 2× — arm, then start) — the watcher builds
   `Vnn_<text>.gcode` and beeps.
5. Start it like any file. Two colors: print pauses with M600 after all base
   plates — load color 2, RESUME purges into the purge tower, the text goes
   on top. Every label is an exclude object (skip single labels live).
Details: ch. 5.2.

**Scenario I — plotting an image (pen instead of nozzle)**
1. Mount a pen (Tools > Plotter > Pen offset X/Y/Z tells the system where it sits).
2. Upload `bild.png` (or .jpg/.svg/.pdf/.txt) — plain, **no `.gcode` tail**
   anymore (.103). Select it in the file list → the watcher generates
   `V01_Plot_bild.gcode` on demand (settings: Tools > Plotter;
   auto-contrast finds the ink on any paper tint, dark boards invert
   automatically; Maintenance > gen-out decides selected-for-start vs
   preview only).
3. Start dialog for the generated file (a plot file: AS SLICED = pure pen
   run, AS LEGACY heats only if the extruder is ON).
4. Multi-color plots pause (M0) at every pen change — swap pens, RESUME.
5. Live Tuning > Plotter while plotting: pen speed %, pen Z ±0.05, X/Y shifts.
Details: ch. 5.3.

**Scenario J — re-printing a section to test the critical middle**
Same as G, but with Floor 0 / Top 2 / no brim: the section prints directly on
the bed with a solid cap on top — the fastest way to test overhangs or
clearances in the middle of a long part without printing the whole thing.

**Filament change mid-print (M600)**
Live Tuning > Pause & Control > Change (M600) → parks hot, unloads, waits with
LED + sound → load until the sensor clicks → RESUME purges (PURGE_MORE for
15 mm more) → continues.

**Typical console session (Mainsail)**

```
SET_MATERIAL MATERIAL=PETG                      # load preset
SET_OVERRIDE_VALUE NAME=hotend_first VALUE=235  # + ON automatically
TOGGLE_OVERRIDE NAME=hotend_first               # ... or off again
SHOW_STATUS                                    # mode + file type + file parameters
SET_LIVE_MINIMUM_CRUISE_RATIO VALUE=0.5         # confirms: [OK] ... -> Klipper
# during the print (every mode):
SET_GLOBAL_SPEED PERCENT=80
SET_LIVE_RETRACTION LENGTH=1.0                  # one parameter, others stay
PAUSE_AT_LAYER LAYER=17
CANCEL_PRINT                                    # twice within 60 s
```

## 5. The generators: Range, Labels, Plotter, Cable ties, Angles, Lithophanes, ColorPic, Gaskets, Frames, Bricks, Kits & Figures

Thirteen generators turn the printer into a manufacturing tool of its own:
partial prints from any G-code, label plates from typed text, pen plots from
images, cable ties, angle plates / flat connectors, lithophanes and color
pictures from photos, sealing gaskets, picture frames / display cases,
building bricks with the exact system geometry, brick KITS from any sliced
file and assemble-it-yourself figures. All of them write
normal G-code files into the gcodes folder (the watcher builds them in the
background — niced, single-pass, a few seconds), all of them run through the
NORMAL start flow, and all generated objects are exclude-objects (skippable
live).

One quality rule applies to every one of them (field-log rule): **the nozzle
never travels over an open hole or slot without retracting — no matter how
short the hop.** Every opening is a registered keep-out: label and screw
holes, the cable-tie head channel and the loop slot, the gasket groove, the
backplate keyhole and stud holes, the frame view opening and the
bridge-test spans. FLAT gaskets and lithophanes have no openings at all —
one continuous bead per layer, nothing to cross.

### 5.0b Generated files: names, versions, select + delete (R133f)

**Names & versions (.118/.120).** Every generated file is named
`V<number>_<name>.gcode` — the running number LEADS, free of the old `00_`
prefix (gone since .120 — three more name characters on the 15-character
display): `V07_R2-D2.gcode`, `V03_Bridge_150mm_40pct.gcode`,
`V01_Figure_s100_SINGLE.gcode`. Why: the LCD shows only the first ~15
characters of a file name — with the number at the end (pre-.118) a
regeneration looked exactly like its predecessor, and frame plates A/B were
indistinguishable. Now the leading number alone tells any two files apart,
and the number is ONE folder-wide counter: it never repeats inside a folder,
regenerating never overwrites an older file (a deleted highest number gets
reused), and it continues above every legacy file that still
sits in the same folder. Both LCD browsers additionally hide the `.gcode`
tail — 6 more characters of real name per line.

**Output folders (.107).** Every generator writes into its OWN subfolder of
the gcodes directory — `Labels/`, `CableTies/`, `Angles/`, `Gaskets/`,
`Frames/`, `Litho/`, `ColorPic/`, `Bricks/`, `Kit/`, `Figures/`, `Plot/`,
`Range/`, `Texture/`, `Towers/` (calibration/test prints). The root stays
clean for your sliced files and sources. The LCD file browser and Mainsail
navigate the folders natively; the Gen files list shows the file name and
selects/deletes via the relative path. Nothing moves on the update: existing
outputs stay in the root and keep working — numbering is folder-local since
.118 (each folder counts its own `Vnn_` files plus the legacy
`00_Name_Vnn` files inside it and takes the next free number).

**Tools > Gen files.** Every generator output, newest first, right on the
display: press a slot to SELECT that file (the start dialog catches it —
nothing prints unasked), or open **Delete file** and press a slot TWICE
(first press arms, second deletes). Only generated files (`Vnn_`/`00_`
names) can ever be deleted this way — your own sliced files are untouchable.

### 5.0 After generating: QUEUE or PREVIEW only (.84)

Every generator (range, labels, plotter, cable ties, angles, lithophane,
colorpic, gasket, frame, bricks, brick kit, figures, texture, bridging test,
resonance plots) finishes by asking
one question: what should happen with the new file? **Tools > After gen**
sets the sticky answer — and every generator takes a per-run `OUT=` to
override it once:

| Mode | What happens |
|---|---|
| **QUEUE** (default) | the new file lands in the print queue: it is selected for printing right away — the LCD start selection jumps to it, you press Print and the start dialog opens. If the generator worked ON a selected file (range excerpt, texture), the new file REPLACES the selection |
| **PREVIEW** | the file is only written and selected for the 3-D preview on the Pi (Mainsail/Fluidd) — nothing is queued, the current selection stays untouched |

Console/Mainsail: `_GEN_OUT_SET OUT=QUEUE` (or `OUT=PREVIEW`,
`OUT=SELECT`, `OUT=1/0`), per run e.g. `GEN_CABLE_TIES COUNT=8 OUT=PREVIEW`.
The setting survives a reboot (default QUEUE — the pre-.84 behavior).

### 5.1 Range — print a section of an existing file

Perfect for re-printing a broken section, testing the critical middle of a
long print, or making a part from just a few layers. Find it in
**Pre-Print > Range/Stop** (the planned stop-at-layer lives in the same menu;
Live Tuning > Pause & Control has the Stop@ shortcut).

**Operation**

1. Select the source file — the menu caps From/To to the file's REAL layer
   count (shown as `File: 123 L`).
2. Set **From** / **To** (From clamps to ≥ 2, To to the file's total).
3. Optional: **Floor**, **Top**, **Brim** and their shapes/fills.
4. > **Create** — a beep confirms; the watcher builds
   `<name>_L<from>-<to>.gcode` and the file AUTO-SELECTS itself (the source
   file's selection is replaced — nothing is deleted).
5. Start dialog → AS LEGACY (recommended: mesh + purge + your pre-print
   settings) or AS SLICED (source temperatures 1:1).

**What the excerpt contains**

- layer FROM prints as the FIRST layer at Z 0.2 ON THE BED (always 0.2,
  whatever the source layer height is — global Z shift, original spacing kept)
- a `PRINT_START` header with the source temperatures → the NORMAL start flow
  (dialog, mesh, purge, first-layer rules: fan off, L1 temps, speed brake)
- its own `_FILE_INFO` at the TOP — Live Tuning > File (G-code) shows the excerpt's values
  from layer 1
- the source fan returns from layer 2 — layer 1 prints without fan
- a real `PRINT_END` at the end: park, stats, fanfare, cooldown — the nozzle
  never stays parked ON the finished print
- the source file's `EXCLUDE_OBJECT_DEFINE` blocks are carried over

**Floor — the glue base under the section (0–10 layers)**

The section usually has no floor of its own; Floor prints a generated raft
under it so it sticks to the bed — the raft edge sits flush with the model
walls (zero gap, it welds directly to the section).

| Parameter | Values | What it looks like |
|---|---|---|
| F.Shape | **FOOTPRINT** | the convex hull of the layer — concavities are bridged over, a compact solid base |
| | **OUTLINE** | the TRUE outline of the layer — concavities and holes stay open, the raft follows the model wall exactly |
| F.Fill | **GRID** | hatch lattice at 45°/135° alternating — the classic look, prints fast |
| | **SOLID** | dense lines that overlap into a solid surface |

**Top — the solid cap over the last layer (0–10 layers)**

Same two switches (T.Shape FOOTPRINT/OUTLINE, T.Fill GRID/SOLID — Top defaults
to SOLID). Prints over the last range layer at the original layer spacing.

**Floor hole — a centered hole in the base (Fl.hole, 0–80 mm)**

For cable feeds — or a lamp: a centered hole with a THICK boss ring around
it, printed as ONE continuous spiral from the hole edge outwards — one bead
of plastic per revolution, no seams, no travel breaks, no strings over the
void (travels that cross the open hole retract first). The hatch stops at the
ring's outer edge. The diameter auto-clamps to the section's REAL outline
(footprint hull or true outline, whichever the floor fills) + a 2 mm margin —
on L-shaped, round or oval sections the boss NEVER sticks out into air; if the
center leaves no room at all the hole is skipped with a console note (every
change is reported).

| Preset | Diameter | Fits |
|---|---|---|
| cable feed | 3–12 mm | zip ties, sensor cables, mains cable with gland |
| **E14** | 15.0 mm | E14 thread passes through (14 mm + tolerance) |
| **E27** | 28.0 mm | E27 thread passes through (27 mm + tolerance) |
| socket body | measure + 0.3 | if the whole lampholder BODY must pass: typical E14 body ~24 mm, E27 ~33 mm — measure YOUR socket |

Print tips: PETG for lamp parts, and for a press-fit thread start 0.2–0.3 mm
below the measured diameter — the boss gives the thread something to bite.

**Top hole — a centered hole in the cap (Top hole, 0–80 mm)**

The tricky one — a hole in a horizontal ceiling means printing over open air.
The generator does it BRIDGE-FIRST: cap layer 1 bridges over the void with an
anchor ring exactly at the hole edge — every clipped hatch line welds onto
that ring, so the edge cannot sag and the hole stays OPEN from layer 1. Layers
2+ open the hole with the same spiral boss as the floor. A top hole auto-raises
Top to 3 layers (bridge + 2 solid) — more Top layers = thicker rim.

**Brim — loops around the start (0–10)**

N loops around the outline, zero gap — the first loop's inner edge touches
the model wall. Key-ring style adhesion helper — printed on the **first
layer** (right at the start of raft layer 1, not after the raft).

**Notes**

- The generated raft counts as INFILL-SOLID, the brim as BRIM — feature
  overrides (speed/accel/flow) work on the generated geometry like on any
  sliced section.
- The excerpt OPENS with the feature that was active at the cut (a
  vase-style source states its `;TYPE:` once in layer 1 — the excerpt
  re-asserts it, so the section never prints as the raft's solid infill).
- The file info (Pre-Print > File info) describes what the EXCERPT really
  contains: features from layers outside the range show as n/a, and the
  per-feature speeds are measured from the excerpt's own layers.
- `;TYPE:` names from OrcaSlicer/Bambu (`gap fill`), PrusaSlicer
  (`External perimeter`, `top solid infill`, …) and Cura (`WALL-OUTER`) all
  map — since R95 also `Overhang perimeter`, `Internal bridge`,
  `Prime tower`/`Wipe tower` and `custom` sections to their features.
- (.127) An UNKNOWN `;TYPE:` spelling maps to **CUSTOM** — the section
  still prints 1:1 (override off), but it is not tunable as the feature
  it really is, and Live > Features shows it under Custom Code. The
  texture tool never touches tags (proven over the 13-dialect corpus):
  if a textured+ranged file shows the outer wall as CUSTOM, the SOURCE
  file's slicer uses a spelling we do not know yet — send the first
  lines of the original and it becomes a mapped feature.
- The excerpt's layer 1 = always 0.2 mm high, whatever the source layer
  height; following layers keep the source spacing.
- Every parameter is also available per console:
  `SET_LAYER_RANGE START=125 END=225 FLOOR=5 FLOOR_SHAPE=1 FLOOR_FILL=1 TOP=3 BRIM=4 FLOOR_HOLE=15 TOP_HOLE=28`
  (shape 0 = FOOTPRINT / 1 = OUTLINE, fill 0 = GRID / 1 = SOLID — the same
  numbers the Range/Stop menu shows as F.Shp/F.Fill)
- E and Z of the body are shifted so the section prints as a standalone part
  in the file's own extrusion mode (relative or absolute E — both work).
- Works with any tagged source file, including multi-object files (EXCLUDE
  handling cleans up cut artifacts at the section borders).

**Stop@ — the planned normal end**

**Stop@ N** (Pre-Print > Range/Stop, or Live Tuning > Pause & Control) ends the print
NORMALLY when layer N begins — stats, fanfare, cooldown, like a finished
print, not a cancel. The natural partner for "print only the first 50 layers".

### 5.2 Labels — the built-in label maker

(.127) **Mirror X / Mirror Y** flip the text in its own label — mirrored
text is what a **stamp** needs. **Stamp** prints a body with the snap
socket under the text (exactly ONE label per job, the label hole is off —
the socket is the mount), **Handle 1/2** adds/reprints the snap handle.
Same fit system as the litho stamp (see 5.6).

Name tags, key fobs, drawer labels, cable markers — engraved text, no slicer,
entirely from the LCD (or one console line).

**The workflow**

1. **Tools > Labels > Text**: up to **5 lines per label** — pick the line (1–5),
   pick the position (Pos 1–N), rotate to the character (Chr), click. A–Z a–z
   0–9 space ÄÖÜäöüß and the common symbols are available; the text prints
   correctly even where the 12864 display can only hint at umlauts. Only
   FILLED lines print — one line simply centers in the free area.
2. **Tools > Labels > Settings**: size, font, stroke, layers, hole … (table below).
3. **Job > Add label** — repeat Text+Add for several DIFFERENT labels (same
   text twice = two identical plates). The queue shows n/24.
4. **Job > Create (press 2×)** — the watcher generates `Vnn_<text>.gcode` (beeps
   when ready) and the file auto-selects. Start it like any file: start
   dialog, adaptive mesh over the labels, purge, your overrides. The same
   text at the same version OVERWRITES its own generated file (settings
   changes replace, they never pile up); a new version number keeps the old
   file for comparison. The uploaded original is never touched.
5. Print sequence is **by layer**: all base plates in color 1 → **M600
   pause** (park, unload — you load color 2) → RESUME purges into the purge
   tower, the text goes on top. Every label is an exclude object, the tower
   too.
6. **Layout**: the hole sits 2 mm from the edge (key rings clip through), the
   text block centers between the three free sides — several lines center as a
   block with gaps that keep the stroke width clear, safe margins to the edge
   and the hole. Max count follows from bed and label size (Fit shows it,
   e.g. `12 (5x3)`); the grid fills left→right, centered; the purge tower is
   placed automatically with 15 mm clearance, on the side your probe does
   NOT sweep (right of the grid — the probe hangs ~43 mm left of the nozzle,
   a tower corner there could catch it and shift layers).

**Settings**

| Setting | Range / values | Meaning |
|---|---|---|
| W × H | label size, default **50×15** | the plate in mm — keychain tags up to near-bed signs (220×220) |
| Font | **SMOOTH · MONO · COND · NARROW · CAPS** | see the font table below |
| Lines | 1–5 | text lines per label |
| Size | 0 = auto, or a cap height in mm | 0: the font fills the label (~94 %). An explicit cap height is a TARGET — the label GROWS so it fits |
| Spc | letter spacing in mm | extra spacing between letters |
| Stroke | 0 = auto, or mm | the letter LINE WIDTH. 0 = auto (three extrusion lines, solid letters) or your nozzle diameter (0.6 = single-line letters). Capped automatically at ⅕ of the cap height — thicker strokes would merge the letters |
| ~ | auto | the version in the file name bumps ITSELF (V01, V02, ...) - regenerating never overwrites an older file; the old Vers setting is retired (R133f) |
| Base / Text layers | e.g. 4 + 2 | plate thickness and text relief |
| LH / 1st | layer heights | base layer height / first layer |
| Ironing | ON/OFF | smooths the text surface |
| Hole | NONE/LEFT/RIGHT/TOP/BOTTOM + diameter | the key-ring hole, 2 mm from the edge |
| Brim, 2 colors, Gap | — | adhesion, two-color mode, spacing in the grid |

**Auto-fit and auto-grow:** the font is sized to use ~94 % of the label with a
5–10 % margin to the border AND the hole. If the letters would drop below
~2.8 mm caps — or an explicit size does not fit — the LABEL GROWS (width
first, then height, up to bed size) instead of erroring. The text is never
shortened; the "needs X mm" errors of old versions are gone. Between glyphs
the head retracts (discrete letters, no ooze ghost lines); the stroke never
exceeds ⅕ of the cap height (anti-merge). The console shows the final
(possibly grown) size and the effective stroke when it was capped.

**The five fonts** (specimen page in the PDF manual)

| Font | Character | Best for |
|---|---|---|
| **SMOOTH** | proportional, handwriting-like — the all-rounder | normal labels, mixed case |
| **MONO** | even single-line strokes, technical | numbers, codes, alignment |
| **COND** | Oswald: condensed, tall x-height | SMALL text — more characters per mm at the same readability; the small-label workhorse |
| **NARROW** | Roboto Condensed: clean, narrow, neutral | small text with a technical look |
| **CAPS** | Bebas Neue: display capitals — everything prints as capitals (`Garage!` → `GARAGE!`) | key fobs, name plates |

COND, NARROW and CAPS are the small-text fonts: narrow glyphs with a tall
x-height keep their readability at 2.8–3 mm caps where SMOOTH starts to blur.
**Fit preview (Tools > Labels > Settings > `Preview fit?`):** answers with the REAL
numbers the generator will print — final label size including growth, cap
height, effective stroke, ~characters per line, and for a fixed Size the
MINIMUM label size it needs (e.g. `for 12mm caps make the label >= 228x17mm`),
plus warnings (stroke capped, purge tower does not fit, plate exceeds the
bed). The LCD keeps the short form (e.g. `80x17+ 3.7`). The instant estimate
in Tools > Labels > Text is a rough guess — the exact numbers follow ~2 s later in
the console.

**Console one-liner (everything optional):**

```
GEN_LABELS TEXT="WERKSTATT~KELLER|VASE" W=60 H=30 FONT=COND SIZE=8 SPACING=1 LINES=2 HOLE=LEFT HOLE_D=5
```

(`~` = line break within a label; `|` separates several labels of one job)

**The label round of .129 (R170) — layout, live fit, split, handles:**

- **LIVE FIT (no button anymore):** Settings shows `Now: 80x17mm Caps 3.7`
  at the very top — it updates ~2 s after EVERY text/font/size/shape/hole
  change. GROW shows the size the print will really have (grown, INCLUDING
  the hole); FIXED shows W/H with the auto-fitted cap height. The W/H input
  minimums follow live (they never block the size your text needs).
- **The 1 cm labels are real:** H goes down to **10 mm** (was locked at 15),
  W down to 12 mm. `Gap` has a **10 mm floor** in every direction — your
  rule from the field report, checked against the printer's bed.
- **NO MORE OVERLAPS (field report .128):** grown and per-job labels kept
  their shelf positions but the uniform grid overwrote them — labels
  printed on TOP of each other (a 94 mm label ended 21.6 mm inside its
  neighbor). Fixed + proven: 14 mixed jobs (one grown to 94 mm) → zero
  overlaps, ≥ 12 mm clearance everywhere.
- **OVERFLOW SPLITS (your choice):** too many/too big labels no longer
  error — the job splits into part files in reading order (`..._T1`,
  `..._T2`, every part a complete plate with its own purge tower). The job
  message names every part, and the Queue row shows `14 -> 2 files` LIVE
  while you build the queue.
- **Handle 0–3 (your choice, Labels AND Litho use the same numbering):**
  `0` none · `1` **ON THE PLATE** with the stamp — printed LAST on every
  layer (the nozzle never finishes on a label it could rip off), z-hop
  approach, 12 mm clearance, its own `GRIFF` exclude object, own brim,
  bridged bore ceiling · `2` separate handle file (as before) · `3` handle
  ONLY (reprint a lost one). Litho refuses `1` with a pointer (its plate is
  FLAT — the handle lives in its own file there).
- **Loud errors:** label refusals show their REASON on the display
  (`M117 Err: Stamp = exactly ONE label …`), and the job menu carries a
  `! Stamp needs 1 label` guard row while the queue breaks the rule.

### 5.3 Plotter — images, photos and text with a pen

Mount a pen instead of (or next to) the nozzle and plot images, photos,
vector graphics or text — no slicer involved.

**Files — the name is the switch**

| Select in the file list | What the watcher generates |
|---|---|
| `photo.png` | PNG → `V01_Plot_photo.gcode` (pen lines) |
| `foto.jpg` | JPEG (baseline; progressive photos refuse — export as PNG) |
| `drawing.svg` | SVG vector graphics |
| `plan.pdf` | vector PDF |
| `notes.txt` | text → auto-wrapping, auto-shrinking page |
| options in the name | `bild.c3.s035.png` = 3 shades, 0.35 mm hatch (defaults c2 / s040) |

**What the converter does for you**

- **Auto-contrast (Otsu)** finds the paper/background — yellowed, grey grid
  paper, light blue — and makes it white: only the dark ink gets plotted.
  Photographs of hand sketches just work.
- **Dark backgrounds just work**: digital writing boards (black background,
  greyish writing), chalk photos, negatives — the converter samples the image
  border; a dark border with a brighter interior means INVERT, the bright
  strokes become the ink. `Invert: AUTO/ON/OFF` in the menu (applies at
  conversion time); the decision is logged in the file header.
- **Text files**: auto-wraps and auto-shrinks to fit ONE page (letters 7 mm
  down to 1.8 mm), umlauts print correctly, unknown characters become `?`.
- **Status on paper**: Tools > Plotter > **> Plot status** (`PLOT_STATUS`) draws the
  SHOW_STATUS report — version, mode, material, temps, PA, flow, speed, accel,
  input shaper, mesh, active overrides — on one page.

**Plotter menu** (in **Tools**)

- DRAW lines vs **DOTS stipple** (fine pencil lines), dot gap
- pen **offset X/Y/Z** (pen next to the nozzle), **scale X/Y in %** (auto-
  capped at the bed limits — you can never scale beyond the bed), bed corner
  limits, **extruder ON/OFF** (draw with filament instead of a pen — heats up
  then), Z up/down, speeds, max size, auto-contrast
- **Drive frame test** drives the pen around your configured bed frame once —
  verify the limits with a real line
- **Start (overrides)**: speed %, pen Z, X/Y shift applied at every plot start
- **Plot text file**: LCD name editor for `PLOT_TEXT FILE=...`
- everything is centered on the bed automatically

**Plotting**

1. Select the file → start dialog: AS SLICED = pure pen (no purge); AS LEGACY
   heats when the extruder is ON.
2. Multi-color plots pause (M0) at every pen change — swap, RESUME.
3. **Live tuning works while plotting**: speed %, acceleration, pen Z ±0.05,
   X/Y ±0.5 shifts (Live Tuning > Plotter). Pen pressure = the usual
   babystepping Z entries.

**Resonance plates and other generated plots:** the calibration chapter
(10.4) shows how the shaper diagrams are PLOTTED or printed as thin plates —
the plotter is part of the calibration toolset too.

### 5.4 Cable ties — the built-in cable-tie maker

Printable cable ties in ONE file, straight from the LCD — no slicer, no
modeling. Each tie is a flat strap with a normal, small closure head like a
shop-bought cable tie: thread the chamfered tip in, pull tight, cut off the
excess. Head size, slot clearance, tooth pitch and bead spacing ALL
auto-scale with the strap width — you never tune the mechanism itself.

**Two closure variants (Setting: Closure)**

| Variant | How it closes | How it opens |
|---|---|---|
| **CLASSIC** | the normal cable tie: a small pawl in the head reaches into the slot, the strap's teeth ratchet past it — pulls tight, locks at every tooth | one-way: cut to remove |
| **LOOP** | a frame loop with an open slot plus beads along the strap — pull the tip through, it snaps over each bead | lift the strap back out of the loop — adjustable at every bead, **reusable** |

**The workflow (LCD: `Tools > Cable ties`)**

1. **Settings** — Count, Length, Width, Layers (strap thickness), LH (layer
   height), Closure, Brim, Vers (see table below).
2. **Create (press twice)** — the first press arms (`Again = start` on
   the display, 10 s window), the second starts the build with a short
   start chirp; then the watcher builds
   the file in the background (niced, ~1–3 s). The happy tune plays and the
   file **auto-selects**: `Vnn_Ties_<len>x<wid>_<CLA|LOO>.gcode` — it
   sorts to the TOP of the file list.
3. Start it like any file: start dialog → AS LEGACY or AS SLICED. The message
   lists everything that was auto-adapted (head size, slot, tooth pitch).

**Settings**

| Setting | Range | Meaning |
|---|---|---|
| Count | 1–24 | ties in ONE project file; the grid arranges them automatically (all fit the bed or you get a clear error) |
| Len | 50–300 mm | strap length. Rule of thumb: bundle circumference + head + a few cm of pull-in reserve |
| Width | 2–12 mm | strap width. The head auto-scales: at width 8 the head is ~12.5×10.6 mm, the slot is width + 0.5 mm, the tooth pitch ~0.45×width. Under 3.6 mm a 0.4 nozzle prints the teeth crisper (the message reminds you) |
| Layers | 3–6 | strap thickness in layers. 3 = flexible, 6 = stiff, strong band |
| LH | 0.12–0.32 mm | layer height. 0.12–0.16 = smoother teeth (finer ratchet steps) |
| Closure | CLASSIC / LOOP | one-way pawl vs adjustable bead loop (see table above) |
| Brim | ON/OFF | loops around each head on layer 1 — the thin head sticks better |
| ~ | auto | the version in the file name bumps ITSELF (V01, V02, ...) - regenerating never overwrites an older file; the old Vers setting is retired (R133f) |

**What prints** — CLASSIC: each tie gets a small box head (solid floor, two
channel walls, a ceiling) with a pawl strip at the channel entry, plus the
strap with stepped teeth on top (a low ramp climbs in, the steep flank
locks). LOOP: a frame with an open slot and a strap with diamond beads —
each bead is a light snap-fit detent that still holds under pull. Every tie
is an **exclude object** (`TIE_1..n`) — skip a failed one live in Objects.

**Material matters (thin flexing parts):** PETG or TPU bend best and hold
tight loops; PLA works for gentle curves and fixed mounts only. Print slow
on layer 1 (the standard first-layer brake applies) and let the fan run from
layer 2 (the file sets it itself).

**Console one-liner (Mainsail — every parameter optional):**

```
GEN_CABLE_TIES COUNT=6 LENGTH=120 WIDTH=8 LAYERS=3 VARIANT=CLASSIC LAYER_H=0.2 BRIM=1
```

`VARIANT=CLASSIC` (one-way) or `VARIANT=LOOP` (adjustable, reusable). Example:
`GEN_CABLE_TIES COUNT=12 LENGTH=100 WIDTH=3 VARIANT=LOOP` = a dozen fine
reusable 100 mm ties for cable management.

### 5.5 Angles & flat connectors — structural plates

Angle plates (L-brackets in ANY angle, equal or unequal legs) and flat
connectors (two boards joined side by side) — screw-on, printable, with a
fully automatic hole layout. LCD: `Tools > Angles+Flat`.

**Mode (the first menu entry)**

| Mode | What it builds | Typical use |
|---|---|---|
| **Angle (L)** | two legs at the set angle (30–170°), leg lengths A and B independently | inside corners, frames, kickers, brackets |
| **Flat splice** | one straight strip of length A+B | joining two boards flat: LEFT/RIGHT = the two halves, each screwed with the SAME hole pattern |

**The hole system — auto-arranged, auto-clamped, never broken**

- Holes sit on each leg's centerline, evenly spaced between the corner zone
  and the leg end — you set only the COUNT and the DIAMETER.
- The diameter can never exceed the leg: it is clamped to `width − 6 mm`
  (≥ 3 mm material around every hole) and to 10 mm. If it was clamped, the
  result message says so.
- If the leg is too short for the requested count, the count drops
  automatically (e.g. 3 → 1 on a short B leg) — the message lists every
  reduction.
- In FLAT mode both halves carry the SAME pattern (mirrored): the parameters
  of one side transfer to the other, so both boards always match.
- **Countersink ON/OFF:** ON adds a two-step cone (two top layers) so
  flat-head screws sit flush; OFF = straight hole for screw head + nut.

**Walls, infill, ironing — the strength dial**

- **Walls 1–6**: concentric loops per layer (outer + inner walls). Wall
  thickness = walls × line width — 4 walls at a 0.6 nozzle ≈ 2.6 mm. The
  number auto-reduces when the leg is too narrow (console reports it).
- **Infill 20–100 %**: 100 prints the classic solid hatch; lower values widen
  the line spacing — lighter plates that stay strong because the walls carry
  the load around the holes. 40–60 % is a good everyday setting.
- **Ironing ON**: one slow, low-flow pass over the top face after the last
  layer — smooth, even surface (skips the countersink cones automatically).
- The hatch inside the walls alternates 45°/135° per layer (cross-lamination)
  and every hole keeps its keep-out — stability = walls + cross-hatch + rib.

**Stiffener (angle mode only; hidden in FLAT mode)**

| Value | What it adds |
|---|---|
| 0 — None | flat plate, the thinnest option |
| 1 — Gusset rib | a triangle over the corner on top of the plate — the standard stiffening; roughly half the plate height |
| 2 — Stepped rib | gusset plus a second, smaller one on top — strongest, for large angles under load |

**Settings (all of them, in menu order)**

| Setting | Range | Meaning |
|---|---|---|
| Mode | Angle / Flat | bracket vs straight splice (see above) |
| Angle | 30–170° | only in Angle mode — hidden in Flat mode |
| Leg A / Left | 20–150 mm | first leg (from the corner) / left half of a flat splice |
| Leg B / Right | 20–150 mm | second leg / right half — set both equal for a symmetric splice |
| Width | 8–60 mm | leg width (the plate's depth) |
| Layers | 4–12 | plate thickness in layers |
| LH | 0.12–0.32 mm | layer height |
| Holes | 0–6 per leg | screw holes per leg (auto-reduced if they do not fit) |
| Hole D | 2–10 mm | hole diameter (auto-clamped to the leg width) |
| Holes: countersunk / normal | toggle | flush flat-head screws vs straight through-hole |
| Rib | None / Gusset / Stepped | corner stiffening (angle mode only) |
| Walls | 1–6 | concentric wall loops per layer — wall thickness = walls × line width (auto-reduced on narrow legs) |
| Infill | 20–100 % | 100 = solid hatch, lower = wider line spacing (the walls carry the load) |
| Ironing | ON / off | one slow, low-flow pass over the top face — smooth finish |
| Count | 1–12 | plates in ONE project file |
| ~ | auto | the version in the file name bumps ITSELF (V01, V02, ...) - regenerating never overwrites an older file; the old Vers setting is retired (R133f) |

**The workflow**

1. Mode → Settings → **Create (press 2×)** — first press arms
   (`Again = start`), second press starts (start chirp). The file appears
   after ~1–2 s,
   auto-selected: `00_Angle_<deg>deg_<A>x<B>_V<xx>.gcode` or
   `00_Flat_<A+B>x<width>_V<xx>.gcode`.
2. The ready-message summarizes the plate AND every automatic adjustment
   (clamped diameter, reduced hole count) — nothing adjusts silently.
3. Start like any file; each plate is an **exclude object** (`PLATE_1..n`).

**Sizing rule of thumb:** the corner zone of an angle is as wide as the leg
(the legs overlap there) — the first hole sits ~width + hole/2 + 1.5 mm from
the corner. For a 90°/40/40 bracket with 4 mm screws that leaves ~1–2 holes
per leg; use longer legs for more screws.

**Console one-liner (Mainsail — every parameter optional):**

```
GEN_ANGLES COUNT=2 ANGLE=90 LEG_A=60 LEG_B=60 WIDTH=25 LAYERS=6 HOLES=2 HOLE_D=4 CS=1 STIFFENER=1 WALLS=4 INFILL=60 IRONING=1 FLAT=0
```

`CS=1` = countersunk, `CS=0` = normal holes. `FLAT=1` switches to the flat
connector (ANGLE is then ignored). Examples:
`GEN_ANGLES ANGLE=135 LEG_A=70 LEG_B=40 WIDTH=30 HOLES=3 STIFFENER=2` = heavy
135° bracket with stepped rib; `GEN_ANGLES FLAT=1 LEG_A=50 LEG_B=50 WIDTH=25
HOLES=2 HOLE_D=5 CS=0` = plain 100 mm splice strip.


### 5.6 Lithophanes — photos that glow

Turn any picture into a back-lit relief print: dark areas print thick, light
areas thin — held against a lamp or window the photo appears. No slicer, no
modeling, no manual image editing: the generator takes the picture as-is and
does the optimization itself (contrast stretch, smoothing, mirror for the
correct viewing side).

**Stamp mode (.127)** — press photos into clay, wax or soap: set
**Stamp ON + Mirror X ON** (FLAT). The generator prints a ~5 mm body with
a snap socket in its underside under the mirrored relief; the optional
**handle** (own file, `Handle 1`) snaps in and holds firm for stamping —
push in until the tip rests on the socket ceiling and the lip clicks into
the groove. Text stamps: **Labels** can do the same (`Labels > Settings >
Stamp`, one label per job, mirrored text).

**The workflow (LCD: `Tools > Lithophane`)**

1. **Upload a picture** — drop any `.png`/`.jpg`/`.jpeg` into the gcodes
   folder (Mainsail drag & drop). The **Images** list refreshes on its own
   (newest first, 10 slots). Pictures you uploaded for **pen plotting are in
   the same list** — the original is never touched, plotting keeps working.
2. **Settings** — Orient, Height/Size, Layer, Levels, Colors, Frame, Brim,
   Ironing (see table).
3. **Slot press = Create (press 2×)** — first press arms the slot, second
   press starts it (start chirp); the watcher generates in its own
   background thread (big pictures ~a minute, the printer keeps serving
   previews meanwhile), the happy tune plays and the file **auto-selects**:
   `00_Litho_<name>_V<xx>.gcode`.
4. Start it like any file. The message reports the plate size, layer count,
   thickness range and the level count.

**Settings**

| Setting | Range | Meaning |
|---|---|---|
| Orient | STANDING / FLAT | STANDING (default): on edge, the classic recipe — most detail, layer lines run with the image. FLAT (.83, step print since .90): the plate lies on the bed — back glass-flat, the top carries the image as clean gray STEPS (full layers, no wavy relief; optional Ironing smooths each step). Ideal as a frame Disc: set Size to the photo size |
| Height / Size | 30–200 mm | **the picture, in the bed plane (FLAT: XY)** — the value is the picture's Y side in mm, X follows the image's aspect ratio (both clamp to the bed). STANDING: the value is the picture height = the print height in Z (one image row per layer). The height in Z is never a size input: **it is the relief — layer count × layer height** (0.7–3.0 mm) |
| Layer | 0.08–0.2 mm | 0.12 = default; 0.08 = maximum detail, roughly double the print time |
| Levels | 0–12 | 0 = continuous grey shades (photo look). 2–12 = posterized: the picture is reduced to N brightness steps — chunky retro look at 2–4, subtle terraces at 8–12 |
| Color swap | OFF / LAST / EACH | FLAT only: OFF = one filament for every step. LAST = M600 right before the DARKEST step — the classic: white body, black contour lines. EACH = M600 at every step boundary. Whenever swaps are on, a purge tower (12×12 mm, 15 mm probe clearance) prints alongside and takes prime + wipe after every change |
| StepL | 1–30 | layers per gray step (FLAT): step 0 = the whole light background as full layers, every darker step prints its region on top, the darkest = the contour lines |
| Frame | ON/OFF | border frame that holds the thin plate straight (recommended) |
| Brim | 0–10 loops | anchors the plate — STANDING to the bed, FLAT against warping |
| Ironing | ON/OFF | slow smoothing pass over the light side (STANDING: front; FLAT: every step cap) |
| Border | 0–10 mm | FLAT: a picture frame around the plate at full height — 0 = off (the old Frame switch maps to 2.4 mm) |
| Corner | 0–20 mm | FLAT: rounded frame corners (0 = square; only with a border) |
| Contrast | ON/OFF | extra contrast boost after the stretch — pushes midtones apart so level edges stand out (sketches, logos, text). OFF = the raw gray values |
| Mirror X | ON/OFF | (.127) flips the picture left-right — **a stamp prints MIRRORED**: the relief is pressed face-down, only a mirrored plate stamps a correct imprint |
| Mirror Y | ON/OFF | (.127) flips the picture up-down |
| Contour | 0–3 | (.127, FLAT only) 0 = walls + fill (default). 1 = the LAST layer prints only the top step's contours (outer AND holes), no fill. 2 = **CONTOUR RELIEF**: step 0 stays a clean solid plane, every darker step prints only its contour lines as raised walls on it — taller = darker, like a topographic map; holes get their own inner contour (a ring prints BOTH contours). 3 = fill as always, but the step walls become the true contours (holes walled too) |
| Stamp | ON/OFF | (.127, FLAT only) a **stamp body** prints under the picture: ~5 mm tall (StampH), ~10 % infill, solid top skin — and a centered **snap socket** in the underside. Press the finished stamp into clay, wax, soap… The header notes it when the picture is UNMIRRORED (your choice, no hidden flip) |
| StampH | 4–12 mm | (.127) the stamp body height (the socket sits inside it, auto-raised if too thin) |
| StampFit | 0.10–0.50 mm | (.127) the socket's radial clearance per side — 0.25 = standard: looser = easier snap, tighter = firmer hold. The fit is MEASURED from the generated g-code (tools/r168_stampcheck.py), not believed |
| Handle | 0/1/2 | (.127) 0 = none. 1 = an extra **handle file** (own g-code — print it when you want it, it never wastes filament with the stamp). 2 = handle ONLY (reprint a lost one). The handle snaps into the socket — no rotation, no thread: a hollow tipped spigot with a groove locks under the socket lip; every surface is vertical or 45° |
| ~ | auto | the version in the file name bumps ITSELF (V01, V02, ...) - regenerating never overwrites an older file; the old Vers setting is retired (R133f) |

**How it prints (STANDING)** — upright, one picture row per layer (the layer
lines run WITH the image, that is what keeps the detail). Thickness runs
from 0.7 mm (brightest, glows first) to 3.0 mm (shadows), 100 % solid —
the file sets everything itself: slow walls, fan curve, PRINT_START. The
plate is one **exclude object**.

**How it prints (FLAT, step print since .90)** — lying on the bed: the
back is glass-flat, and the picture is quantized into `Levels` gray steps
that print ONE AFTER ANOTHER as full layers: step 0 = the whole light
background (one clean surface — iron it), every darker step its (nested)
region on top, the darkest step = the black contour lines. Nothing ever
prints over air (each region lies completely on the step below), the nozzle
never dives into a wavy relief and the probe never catches on steps. The
file is `00_LithoF_<name>…`. The classic sketch recipe: white background
image + Levels 3 + Color swap LAST = white body with black lines.
**Sizes:** the Size input sets the picture in **XY** (the bed plane) —
X follows the image aspect, both clamp to the bed. The height in **Z is
not a size**: it is the relief — the layer count × layer height (the
thickness range dark→light). Both modes hard-clamp to the bed (aspect
kept) — a value can never produce an oversized plate.

**Material & light:** white or natural PLA glows best. The effect unfolds
with back-light 20–50 mm behind the plate (window, LED, tea light with a
diffuser). Big plates above ~120 mm can be printed in two halves and glued.

**Housekeeping** — `Delete image` (2-press confirm: press the slot, press it
again) removes the picture from the folder. Its **plotter `.gcode` stays** in
the file list — only the image goes away. Console: `LITHO_CREATE INDEX=0`
(first image slot) or `LITHO_DEL_SLOT INDEX=2`.

### 5.7 Gaskets — the built-in seal maker

Sealing rings straight from the LCD: outer/inner diameter and height, with a
flat face or a groove that raises the contact pressure. One continuous
spiral per band — no seam, no start-stop blob where a seal would leak, and
no string ever dragged across the open groove (crossings retract, even the
short band-to-band hop between the lips).

**The workflow (LCD: `Tools > Gaskets`)**

1. **Settings** — OD, ID, Height, Face (FLAT/NUT), Ironing, LH, Vers.
2. **Create (press 2×)** — arm, then start; the watcher builds the file in
   seconds, the happy
   tune plays and the file **auto-selects**:
   `00_Seal_<od>x<id>x<h>_V<xx>.gcode`.
3. Start it like any file.

**Settings**

| Setting | Range | Meaning |
|---|---|---|
| OD | 12–200 mm | outer diameter — measure the flange face, not the pipe |
| ID | 6–190 mm | inner diameter; the ring band must be ≥ 2.4 mm wide |
| Height | 0.4–6 mm | 1.2 mm = standard flat gasket; 2 mm+ recommended for NUT |
| Face | FLAT / NUT | FLAT = full contact face. NUT = a groove in the face leaves two raised sealing lips — higher pressure, seals better on uneven/flanged surfaces (falls back to FLAT with a note if the band is too narrow) |
| Ironing | ON/OFF | slow smoothing pass over the sealing face |
| LH | 0.12–0.32 mm | layer height; 0.12–0.16 = smoother face |
| ~ | auto | the version in the file name bumps ITSELF (V01, V02, ...) - regenerating never overwrites an older file; the old Vers setting is retired (R133f) |

**Material:** TPU seals best (the file already prints at 15 mm/s), PETG
works, PLA only for dry, low-pressure lids. Dry the filament — moisture
bubbles are the #1 seal killer.

**Console one-liner (Mainsail):**

```
GEN_SEAL OD=40 ID=20 HEIGHT=1.2 PROFILE=FLAT IRONING=0
```


### 5.8 Frames — picture frames & display cases

A frame for a photo, or a deep display case for a collectible — printed in
one piece with its backplate, stand and hidden hanging options. The main
design goal: a **uniform, smooth front face** — the frame prints lying on its
back, the visible face points up and gets the ironing pass.

**Placement & first layer (field log .74):** every plate — one-piece, multi
Part A/B, split kit — sits **centered on the usable bed**, never crammed
into the x0/y0 corner. If the frame alone would not fit, the border
hard-clamps to what the bed offers (.83, minimum 6 mm) before the
generator ever thinks about splitting — and the W/H inputs never accept
values above the build volume. The first layer of every part prints in a fixed
discipline: **brim → inner wall → outer wall → one continuous zigzag fill**
(back-and-forth with extruded connectors — singly printed lines curled up at
their starts/ends and frayed the borders). The only travels inside that fill
cross open holes (keyhole, stud holes, cable slot) — and those retract.

**The workflow (LCD: `Tools > Frames`)**

1. **Settings** — Preset (9x13 · 10x15 · 13x18 · A6) or custom W/H, Depth,
   Border, Corner r, Shape, Closure, Hang, Stand, Surface (Front), Disc,
   Cable, Infill, Walls, Vers — each topic is its own submenu, plus
   **Presets** (save/load/delete your own complete frame configurations,
   8 slots).
2. **Create (press 2×)** — arm, then start; the watcher checks the bed fit
   while generating
   (≈ 1 s), the happy tune plays and the file **auto-selects**:
   `V01_Frame_<preset>_FLATx8.gcode` (Part A when the bed needs two
   plates — one beep per plate, the number of beeps = number of files).
3. Start it like any file. Multi-plate: after the last layer of Part A the
   console + LCD say which file is next — **nothing auto-starts**, load and
   start Part B yourself (same material, same settings).

**What a frame consists of**

| Part | Job |
|---|---|
| FRAME | the ring: solid back band → photo groove (with the closure nubs) → bridge shelf → front face with the view opening; the front's last layer is ironed |
| BACKPLATE | 0.8 mm cover plate — 0.3 mm play per side through the photo shaft, snaps under the 4 wall nubs; hidden keyhole (TOP/BOTTOM/LEFT/RIGHT) and, with Stand, two D2.7 stud holes |
| STAND | easel leg with two studs that plug into the backplate holes (24 mm apart) |
| STRIP_T/B/L/R | only in the split KIT: the four frame walls as glue strips |
| Part A / B | multi-plate: when frame + backplate do not fit side by side, the generator writes two files — `Vnn_A_Frame_….gcode` (frame) and the next number `Vnn_B_…` (backplate + stand) — the plate letter sits DIRECTLY behind the version, so the 15-character LCD shows the role (the old tail suffix was cut off); consecutive numbers tell any two files apart at a glance. Part A auto-selects, the end-of-plate hint (console + LCD + beeps) names Part B, no auto-start |

**Settings**

| Setting | Range | Meaning |
|---|---|---|
| Preset / W·H | 40–230 mm | photo inner size (9x13 stays one file up to border 10; 10x15/13x18/A6 print as 2 plates on the 220 mm bed) |
| Depth | 3–60 mm | under 15 = flat photo frame, 15+ = deep display case (same closure system) |
| Border | 4–30 mm | frame width around the photo |
| Corner r | 0–30 mm | corner radius (RECT only; a split kit drops it to 0 with a note) |
| Shape | RECT / OVAL | OVAL = ellipse from W×H (two diameters); no kit split for ovals |
| Closure | BACK / SIDE | BACK = snap-in backplate (.91, .126): the plate has **0.35 mm play per side** measured against the photo shaft's LIGHT size (wall lines print with their center on the contour — the shaft is one line width narrower than the photo contour, the plate half a line wider than its own; .125 and earlier ignored both and the plate was 0.7 mm OVERSIZE). Drop it in, the 4 wall nubs click over its edge with a 0.2 mm overlap — the nubs grow out of the wall at ≤45° over two layers (they used to print as free walls in the groove air). SIDE = photo + plate slide together through the slot in the left wall |
| Hang | TOP/BOTTOM/LEFT/RIGHT/OFF | keyhole position in the backplate — **invisible from the front** |
| Stand | ON/OFF | easel leg; auto-dropped with a note if the bed has no room |
| Front (Surface) | Ironed / Bed texture / Lines / Waves / Honeycomb | the visible face: classic ironing pass, the flipped print (bed texture = the face, no ironing) or a structured border band |
| — structure | Depth 0.4–2.4 mm · Spacing 2–15 mm · Angle 0–90° · Wave amp 0.3–3 mm · Cell 4–20 mm · Dir IN/OUT | Lines/Waves/Honeycomb parameters; OUT = ridges proud of the face, IN = grooves cut into it (RECT only, replaces ironing) |
| Disc | NONE / GLASS / PLEXI / FOIL / LITHO · Side FRONT/BACK · Thick 0.4–6 mm | optional disc insert: FRONT = in front of the photo, captured by a 1.2 mm lip; BACK = behind the photo on the back band (backlit litho) — the groove grows by the disc thickness |
| Cable | ON/OFF | hidden 6 mm cable duct through the bottom bar (display CASE only, depth 15+) — opens 2.5 mm behind the back face straight into the interior, invisible from the front |
| Ironing | ON/OFF | the smooth shiny front pass (only with Front = Ironed) |
| Infill | 5–100 % | frame body infill (the solid faces stay solid; below 100 % the body prints as SPARSE infill — its own feature tag) |
| Top layers | auto / 1–15 | solid layers of the FRONT face (auto = the classic ~1 mm band) — independent of the front effect and the orientation |
| Bottom layers | 0–15 | solid skin at the BACK face (default 2; 0 = infill from layer 1) |

**Bed-fit logic (automatic, real bed 220×220 from `[gcode_macro _R2_CONFIG]`):**

1. frame + backplate side by side fit → **one file** (small formats).
2. they don't, but the frame alone fits → **two plates** (R90.1a): Part A =
   frame, Part B = backplate (+ stand). Nothing is glued, the finished
   frame is identical to the one-piece print.
3. even the frame alone overflows the bed (RECT only) → **4-strip glue
   kit** (strips on plate A, backplate on plate B; every part an exclude
   object, the notes say: glue the butt joints with wood glue).
4. still too big, or OVAL that doesn't fit → a clear console message with
   the border limit — the guard beeps and shows on the LCD, nothing
   half-fits and no file is written.

**Assembly (BACK):** photo lies flat onto the back band, backplate goes in
with its edge notches at the left/right nubs, slide 2.5 mm — locked, no
tools, no flex. **(SIDE):** photo + cover plate slide together into the left
wall slot. The hang keyhole works with a normal nail or screw head.

**Console one-liner (Mainsail):**

```
GEN_FRAME PRESET=10x15 DEPTH=8 BORDER=12 SHAPE=RECT CLOSURE=BACK HANG=TOP STAND=1
GEN_FRAME PRESET=10x15 DEPTH=20 CABLE=1 DISC=PLEXI DISC_T=1 DISC_SIDE=BACK
GEN_FRAME PRESET=9x13 FRONT=HEX S_SIZE=9 S_DIR=IN
```


### 5.9 Texture: fuzzy skin & shaped bumps (any g-code file)

The only generator that does not create a part — it rewrites the **outer
wall of a file you already have**. Two looks:

- **FUZZY** — every outer-wall vertex gets a random offset (a seeded
  scatter, same file + same settings = same result). That is the classic
  "fuzzy skin": matte, grippy, hides small wall flaws.
  *(R95)*: files sliced with **arc fitting** (G2/G3 — vases, cylinders) get
  their arcs flattened into short textured chords first — the texture now
  runs seamlessly around the WHOLE part instead of only in the few straight
  bits between arcs (field log .74: "only the corners"). Each chord carries
  its exact share of the arc's extrusion.

**Fuzzy presets** *(R95, sized after OrcaSlicer's fuzzy skin — thickness
0.3 mm / point distance 0.8 mm by default)*:

| Preset | Thick | Density | After Orca's use case |
|---|---|---|---|
| ORCA def | 0.30 mm | 100 % | standard fuzzy skin (Orca default) |
| Hide layers | 0.25 mm | 100 % | hides layer lines (Orca: 0.2–0.3 mm) |
| Subtle | 0.15 mm | 60 % | subtle matte surface (Orca: 0.1–0.2 mm) |
| Grip | 0.50 mm | 100 % | aggressive grip (Orca: 0.5–0.8 mm) |

LCD: Pre-Print > Texture > **Presets** — or `TEXTURE_APPLY PRESET=LAYERS`.
The thickness range is 0.05–1.5 mm (Orca-sized).
- **BUMPS** — the offset follows a **pattern**: Grid (egg-crate dimples),
  Waves (diagonal ripples **with a z-phase** — the pattern crawls slightly
  from layer to layer, which visually swallows layer lines), Honeycomb
  (hex dimples) or Mandelbrot (a fractal landscape — every spot on the bed
  gets its own bump height, unique per position).

Everything else stays **byte-identical**: `;TYPE:` tags, EXCLUDE_OBJECT,
APPLY_TYPE/LAYER_MARK markers, **E values, Z values, speeds (F)** — inner
walls, infill, ironing and supports print exactly as sliced. Only the
outer skin moves.

**Workflow (LCD):**

1. select the file as always (file list — Mainsail or the LCD; the
   selection preview shows the target),
2. **Pre-Print > Texture**, pick the mode + parameters,
3. **> Apply (beeps)** — the watcher builds the result in the background,
4. a **NEW file** `Vnn_<name>_TX.gcode` appears (the number counts up if you apply
   again — the source is never touched),
5. **check it in the 3D viewer** — nothing auto-starts, by design,
6. print the `_TX` file like any other (AS SLICED keeps the texture).

(.84) Steps 5–6 follow **After gen** (ch. 5.0): QUEUE selects the `_TX`
result for printing and REPLACES the source file's selection (the source
itself stays on disk, untouched); PREVIEW ONLY leaves the selection alone.
In both modes nothing ever starts printing by itself.

| Parameter | Range | Meaning |
|---|---|---|
| Mode | OFF / FUZZY / BUMPS | OFF = the menu is inert (Apply refuses with a hint) |
| Fuz thick | 0.1–0.6 mm | scatter radius (fuzzy) |
| Fuz dens | 10–100 % | share of vertices that scatter (100 = all) |
| Pattern | Grid / Waves / Honeycomb / Mandelbrot | bump shape (bumps) |
| Scale | 3–60 mm | pattern cell size — small = fine orange peel, large = bold dimples |
| Amp | 0.1–0.8 mm | bump depth |
| Dir | OUT / IN | OUT = grows away from the part, IN = cuts into it |

**What the tool will never do:** overwrite the source file · auto-start
the result · move anything but outer-wall vertices · leave the bed
(clamping with a counter) · touch E/Z/F values · run without guards (bad
mode/pattern/direction, missing file, all 99 versions used → clear error,
nothing half-done).

**Special cases (tested):** a file without outer walls (infill-only
parts) → zero shifts, no crash · the very first outer vertex of a file and
zero-length restarts after a retract have **no approach direction** — they
stay untextured instead of guessing one · absolute-E files (M82),
E-only retract lines, G0 travels and CRLF line endings pass through
untouched · OrcaSlicer/Bambu spellings (`;TYPE:Outer wall` in any case)
are recognized.

**Console one-liner (Mainsail):**

```
TEXTURE_APPLY FILE=myfile.gcode MODE=FUZZY THICK=0.3 DENSITY=100
TEXTURE_APPLY FILE=myfile.gcode MODE=BUMPS PATTERN=WAVES SCALE=10 AMP=0.35 DIR=OUT
```

FILE may be omitted — then the **selected** file is the target (same as
the LCD). The result beeps when done (`r2_done`) and shows a console
summary; on error the alarm sounds and the LCD says what to fix.


### 5.10 Building bricks — the exact system geometry (R121)

The printer becomes a brick factory: bricks, plates and tiles with the
**exact geometry of the building-block system** — printed parts clamp to
each other AND to original bricks. No modeling, no slicer: pick parts from
the catalog, CREATE, print.

**Why the parts fit (the three numbers that matter)**

| Element | Measure | Effect |
|---|---|---|
| body | n·8 − 0.2 mm | the 0.2 mm play is the clamp: two parts side by side grip each other, printed next to original parts they clamp the same |
| stud | Ø4.8 × 1.8 mm, hollow (1.2 mm wall) | stacks like the original, prints without a solid blob on top |
| underside tube | Ø6.31 at every inner grid crossing | the tube walls spread over the stud below — the clutch comes out exactly right |
| brick / plate / tile | 9.6 / 3.2 mm heights, tile = smooth plate | layer heights that do not divide evenly snap to whole layers (noted in the file header) |
| layer 1 | solid + brim | bed adhesion; the tubes open from layer 2 up |

**The catalog (45 codes)** — `B`=brick 9.6 mm, `P`=plate 3.2 mm, `T`=tile
(smooth plate): 1x1, 1x2, 1x3, 1x4, 1x6, 1x8, 2x2, 2x3, 2x4, 2x6, 2x8, 4x4,
4x6, 4x8, 6x6, 6x8, 8x8 — first the width in studs, then the length.

**The workflow (LCD: `Tools > Bricks`)**

1. **Catalog** — every code is an entry; the press bumps its count
   (same codes merge, max 120 parts per plate).
2. **Settings** — Layer (0.08–0.32) and Vers, shared with the other
   generators.
3. **CREATE** — the watcher builds the file in its background thread
   (beeps + auto-select): `V01_Bricks.gcode`.

One file = **one color**, every part its own **exclude object** — a failed
brick can be skipped live and reprinted later. Console/Mainsail:
`GEN_BRICKS CODES="B2x4:3|P2x2:2"` (sets the queue and creates in one go).

### 5.11 Brick kit — a sliced file becomes a building kit (R125)

The kit generator reads **any sliced print file** and rebuilds it as a
stylized brick kit: the object is rasterized onto the stud grid and
decomposed into 2-wide bricks (the kit look), printed as plates A, B, C…

**What flows in — and what never does:** ONLY the object. Support,
support interface, brim, skirt and prime-tower moves are filtered out
before the geometry is even built (field rule: the kit is the CLEAN
object). Foreign slicer files work — `;TYPE:` comments and our
`APPLY_TYPE` markers are both understood.

**How the object becomes bricks**

| Step | What happens |
|---|---|
| Voxelizing | the object moves are sampled at 0.8 mm — the system's base unit |
| Bands | MICRO/SMALL: brick bands of 9.6 mm (merged 3 plate layers); BIG: plate bands of 3.2 mm (fine steps) |
| Solid or shell | closed bodies fill solid; hollow bodies (vases, sparse infill < 15 %) become **ring walls** — the silhouette stays, print time drops |
| Decomposition | greedy 2-wide bricks first (2x8 down to 1x1), orientation-resolved |
| Detail AUTO | ≤ 10 studs → MICRO, ≤ 26 → SMALL, else BIG |

**Colors 1–8** (grey, black, red, blue, yellow, green, orange, purple) and
two print strategies:

- **BY_LAYER (plates)** — one color per plate, the plate change IS the
  color change: **zero M600**. Print plate A in grey, plate B in black…
- **BY_OBJECT** — parts print one after another (the file says
  `BY_OBJECT=1`), sorted so that all parts of one color run together:
  M600 only at the color boundaries.

Up to **800 parts**, ~110 per plate; every part its own exclude object.
**The workflow (LCD: `Tools > Bricks > Kit from file`)** — Source (the 5
newest sliced jobs, generator outputs (Vnn_/00_ names) skipped; SRC=filename
via Mainsail),
Detail, Mode, Colors, CREATE. Console:
`GEN_BRICKKIT SRC=box.gcode DETAIL=AUTO MODE=BY_LAYER COLORS=3`.

### 5.12 Figures — assemble-it-yourself (R126)

Stylized figures in the classic proportions (caliper-measured head, torso,
legs) mapped onto the building system: **5 parts per figure** — legs, torso,
two arms, head. Assembly without glue: the torso presses onto the hip tenon,
the arms slide onto the shoulder pins (**they swing**), the head presses
onto the neck post (**it turns**).

**100 % = original size AND system-true:** the hands grip Ø4.8 studs and
axes, hats sit on the head stud, the feet click onto studs (anti-studs
underneath). Other scales (25–300 %) are display figures — only 100 %
mates with the system. Count 1–24, one color, every part its own exclude
object, ~39 mm tall at 100 %.

**The workflow (LCD: `Tools > Bricks > Figures`)** — Scale (25–300 %,
5 % steps), Count, CREATE → `V01_Figures_s100.gcode`. Console:
`GEN_FIGURES SCALE=100 COUNT=2`.

### 5.13 ColorPic — photos in full color, no backlight (R120)

The color sibling of the lithophane: the photo prints **flat** as stacked
color bands, lightest first — every darker band prints only its (nested)
region on top, so the picture needs NO backlight and works from every
angle. The image pipeline is the proven one (percentile contrast stretch +
optional boost), then the picture is quantized into 2–8 luminance bands.

**The workflow (LCD: `Tools > ColorPic`)** — same image list as the
lithophane (upload a `.png`/`.jpg` into the gcodes folder), Width, Bands,
Band height, Colors (per-band palette, light→dark; auto ramps when empty),
Layer, Ironing, Brim, **Swap**, **Contrast**, Vers → CREATE →
`V01_ColorPic_<name>.gcode`.

| Setting | Meaning |
|---|---|
| Bands | 2–8 luminance levels — band 0 = the lightest color and covers the whole area (the base) |
| Band height | each band's thickness in mm (total height = bands × band height) |
| Colors | comma palette codes light→dark (WHT GRY BLK RED ORG YEL GRN BLU PUR BRN PNK CYA GLD SIL); fewer codes than bands = auto-filled |
| Swap | ON (default): M600 at every band boundary — the nozzle LED **blinks from the old to the new color** while you swap, the **purge tower** (12×12 mm, 15 mm probe clearance) takes prime + wipe after every change. OFF: every band prints without a filament change (one color) |
| Contrast | extra boost after the stretch — band edges stand out (sketches, logos, text) |
| Ironing | smoothing pass over every band cap |

Console/Mainsail: `GEN_COLORPIC SRC=photo.png WIDTH=120 BANDS=4
COLORS=WHT,GRY,BLK BANDH=0.8 SWAP=1 CONTRAST=1`.

## 6. During the print: tuning, pauses, objects

Everything that happens between "print started" and "print finished". Live
tuning works in EVERY start mode — including AS SLICED and while plotting.

### 6.1 Live tuning reference

```
Speeds:  SET_GLOBAL_SPEED PERCENT=20..300 (never capped) — ONE global factor; the
         running feature's % re-applies on top immediately
Feature: SET_OVERRIDE_VALUE NAME=feat_spd_<code> VALUE= · NAME=feat_acc_<code> VALUE= · NAME=feat_on_<code> VALUE=1|0
         (16 feature codes) · SET_IRONING_FLOW PERCENT=
Accel:   SET_GLOBAL_ACCEL ACCEL= — the global accel; a feature with its own accel
         keeps it (feature beats the global)
Limits:  SET_LIVE_VELOCITY VELOCITY= (caps the FASTEST moves = travels) · SET_LIVE_ACCEL ACCEL= (global cap,
         travels included) · SET_LIVE_MINIMUM_CRUISE_RATIO VALUE= (each confirms "[OK] … -> Klipper") ·
         SET_LIVE_SQUARE_CORNER VALUE=
Z-Hop:   SET_Z_HOP ENABLE=1|0 HEIGHT=0.1..3 — lifts Z on every firmware retract (G10/G11), lowers
         before the unretract: nozzle-crash protection for towers, text, small parts (.83)
(.127) Live > Features > Custom Code / Overhang Wall / Internal Bridge /
Prime Tower carry the full set (On / File / Speed / Flow / Accel / PA)
like every feature — they were empty lists before (.126 field report
"custom stands empty in it").

Feature PA (.85): SET_FEAT_PA FEATURE=<code> PA=<0..0.3> — pressure advance for ONE feature
         (e.g. wallouter 0.055, infillsparse 0.08); applied at every boundary of that
         feature, the global PA returns when it ends. 0 = off. LCD: Live Tuning > Features > <feature> > PA
Shaper (.85): SET_FEAT_SHAPER_OFF FEATURE=<code> STATE=1|0 — input shaper OFF while that one
         feature prints (sharp corners on slow outer walls), frequencies restored when it
         ends and at PRINT_END/cancel (safety net _FEAT_TUNING_RESTORE). Needs [input_shaper]
Fan curve (.85, .126): SET_FAN_CLAMP ON=1|0 MIN=0..100 MAX=0..100 BRIDGE=0..100 — every M106 of the
         file runs clamped between MIN/MAX percent (a file that wants 100 % gives 90 %), BRIDGE
         lifts the fan while a bridge section prints (0 = off). .126: clamp changes apply
         IMMEDIATELY (they used to wait for the file's next M106 — generated files send ONE per
         print, nothing ever visibly changed) and the BRIDGE boost fires at the feature boundary
         itself (files send M106 at the layer start, never at the bridge), restoring the file
         value when the bridge ends. LCD: Live Tuning > Temps & Fan > Clamp/FMin/FMax/FBrdg
Drive (.107): SET_EXTRUDER_DRIVE TYPE=DIRECT|BOWDEN — the retraction STARTING-POINT profile
         (direct 0.6mm @ 40mm/s + z-hop off / bowden 4.5mm @ 30mm/s). Only a starting point:
         length, speeds, unretract extra + z-hop stay freely editable in BOTH directions,
         pre-print and mid-print. Independent from RetractFix (that repairs old FILES).
         LCD: Pre-Print > Velocity > Retraction > Drive
Unretract (.85): SET_UNRETRACT_EXTRA EXTRA=-1..3 — every unretract adds EXTRA mm of filament
         (seals the dot after a travel; 0 = off). Firmware retraction only
Extrusion: SET_FLOW_RATE PERCENT=1..300 · SET_LIVE_PRESSURE_ADVANCE VALUE= ·
         SET_LIVE_PA_SMOOTH TIME= · SET_LIVE_RETRACTION LENGTH= SPEED= UNRETRACT_SPEED= EXTRA=
Temps:   SET_LIVE_HOTEND_TEMP T= · SET_LIVE_BED_TEMP T=
Fan:     SET_FAN_SCALE PERCENT=      Babystep: BABYSTEP_UP/DOWN[_FINE]
Objects: SKIP_OBJECT OBJECT=name (2x) · SKIP_CURRENT_OBJECT · SHOW_OBJECTS
Compat:  SET_INNER_WALL_SPEED / SET_INFILL_* remain feature-less (inner wall and
         infill print 1:1 - use the global factor)
```

SET_LIVE_RETRACTION mirrors all four values in _STATE — the LCD shows LIVE
values and changing one parameter never clobbers the others.

**Where does a value come from?** `PARAM_SOURCES` (LCD: Live Tuning >
Sources) prints the full provenance for every parameter: **file | your
pre-print override | LIVE in Klipper now** — including PA, velocity, min
cruise ratio, corner velocity, flow, retraction, fan and the L1/L2 temps. The
LCD inputs for flow/accel read the LIVE Klipper values, so a change made in
Mainsail shows on the display and vice versa. The **FeatSpd / FeatOn /
FeatAcc** items edit the feature CURRENTLY printing (which one: the "Now:"
line at the top of Speeds/Accels/Features); if nothing feature-marked is
printing (raft or unmarked section) they say so instead of silently doing
nothing.

**Feature overrides the file cannot use:** at the print start every enabled
feature override whose type is not in the file (TYPES from the file info) is
parked for this print — the console lists them ("Not in this file (overrides
parked for this print): …"). Your switches stay intact for the next file that
really contains those features.

**One global factor.** LCD > Live Tuning > Spd/Acc per feat has exactly one
global entry each (Glob % / Acc) — works on EVERY file, in both takeover
modes and AS SLICED alike. Switch features off individually (never as a
burst — the safe way on a small Pi).

### 6.2 All pauses explained

Every pause parks the same safe way (6.4). They differ in WHEN they fire:

| Pause | Trigger / Condition | After |
|---|---|---|
| User pause | LCD "PAUSE NOW", PAUSE, QUICK_PAUSE, M0/M1 (slicer) | parked, waits for RESUME |
| Start dialog hold | file calls PRINT_START | AS SLICED / AS LEGACY / CANCEL |
| Planned: next layer | PAUSE_NEXT_LAYER | fires at the next boundary; one-shot |
| Planned: at layer N | PAUSE_AT_LAYER LAYER=n (n>1) | one-shot at layer n |
| Runout | sensor empty → next layer boundary → filament mode | load → RESUME purges |
| Filament change | M600 / CHANGE_FILAMENT (printing or idle, heats ≥200 °C) | filament mode; RESUME purges |
| Legacy dialog | old file detected, start_confirm ON | asks AS SLICED / AS LEGACY / CANCEL within seconds (M190/M109 only preheat in the background while it waits) |
| Legacy prep | old file + AS LEGACY, "Old files" ON — once per file | homes, heats bed, meshes, heats to L1 (file value > preset), purges, L1 speed — then GAPLESS continue (pause position restored, no park/return dance, no ooze). Anti-ooze: a hotend already at print temp drops to 170 °C standby during bed + mesh and re-heats for the purge |
| Sequential object | Z falling edge (high-water ≥1.6 → <0.75 mm), layer ≥2; z-hops ≤1 mm are un-ratcheted and never trigger | L1 temps + L1 speed; pauses only if a heater must move, then self-resumes |
| Cancel 1st press | CANCEL_PRINT once | arms; 2nd press within 60 s cancels; RESUME disarms; the arm expires after 60 s — printing OR paused |

**While paused:** heaters KEEP targets · idle timeout "infinite" · filament
sensor disabled · LED paused · LCD shows the reason. Self-healing: if our mode
disagrees with Klipper, the watcher re-syncs after ~5 s.

### 6.3 Resume & cancel

**RESUME — step by step**

1. disarms cancel/skip confirmations
2. returns XY first (safe height), then Z slowly (F300)
3. re-primes ooze compensation (E3 + E0.8 slow) if the hotend is hot
4. re-enables sensor, restores idle timeout
5. re-applies the current feature type (APPLY_TYPE)
6. **re-applies the L1 speed brake while layer 1 runs** — the brake always has
   the last word
7. sound + continue; held files continue via M24

**CANCEL_PRINT (2×):** 1st press pauses + arms; 2nd press within 60 s: lift,
park, heaters off, stats, sad sound. The arm expires after 60 s — printing OR
paused: a forgotten first press can never become an instant cancel later.
Override switches stay as you set them.

**After EVERY end — cancel, PRINT_END, or a legacy file finishing:
_PRINT_CLEANUP** resets all per-print state: cancel/skip/mesh arming, legacy &
as-sliced flags, file type, file-held flag, pause bookkeeping, live tuning
(M220/M221 → 100 %), planned pauses, layer tracking. Deliberately KEPT: your
pre-print settings, the selected material and the loaded bed mesh. The next
print starts CLEAN.

### 6.4 Parking & safe movement

- lift +5 mm, capped below Z max — never rams the frame
- XY to the corner FARTHEST from the objects (file polygons; fallback front
  left)
- anti-ooze retract −3 mm only if the hotend is ≥170 °C
- sensor off, idle timeout infinite
- every move checks homed_axes — unhomed axes are never moved
- Z high-water re-anchored at PAUSE and at every object start — parking can
  never fake an object change

**Homing — when what moves, and who guards it**

- Every start path homes first (G28) — before bed heat, mesh, hotend and
  purge. Afterwards the gantry can sync itself (SYNC_GANTRY — [force_move]
  required; toggles for boot/print start).
- Z offset lives in the probe: Leveling > probe offset (paper method, TESTZ
  ±0.04/±0.12) → SAVE_CONFIG.
- Babystepping during a print (SET_GCODE_OFFSET Z_ADJUST MOVE=1) is
  runtime-only — the saved offset never changes.
- Guard rail: every park/move macro checks homed_axes — unhomed axes never
  move; PAUSE, M600, M0/M1 inherit the same guard.
- START_PRINT (the old macro name): marked files = no-op (PRINT_START prepared
  everything); legacy files = REAL legacy start (home/heat/purge) — old mod
  files depend on it.
- "Must home axis first": the real error is usually ABOVE it in the console
  (ch. 22).

### 6.5 Skipping objects & ending a print early

**Skip a single object** (multi-object prints): Live Tuning > Objects (or
`SKIP_OBJECT NAME=name`, 2× confirm — `SKIP_CURRENT_OBJECT` skips the one
printing right now, `SKIP_DISARM` cancels a pending skip, `SHOW_OBJECTS`
lists all objects with their state). The rest of the print continues; KAMP's
adaptive mesh and the smart parking already know the remaining objects. Works
for sliced multi-object files AND for generated files (labels, ranges,
bridging towers — every generated part is an exclude object).

**End the print normally at a planned layer:** Pre-Print > Range/Stop >
**Stop@ N** (or Live Tuning > Pause & Control > Stop@) — when layer N begins, the
print ends like a FINISHED print: park, stats, fanfare, cooldown — not a
cancel. Combined with the range generator (ch. 5.1) this covers "print only
part of it" in both directions: from the file start up to N, or a standalone
section From–To.

## 7. Filament: load / unload / change / runout / cold pull

- temperatures always right: print temp kept during prints; idle heats ≥200 °C
- load_length 60 mm (LCD 20-150) feeds LOAD_FILAMENT · unload_length 90 mm
  (LCD 40-150) feeds unload AND change — both settable
- **color-change purge (R92):** the 15 mm flush after a change lands as a FLAT
  0.3 mm strip beside the objects (front edge, probe-safe window) — never as a
  blob at the park corner where the micro probe would catch it on the next
  mesh. PURGE_MORE lays another strip the same way.
- repeat runout events while armed are ignored
- **BTT SFS V2.0 (two-part sensor):** switch part `[filament_switch_sensor
  filament_sensor]` = filament end → alarm + planned pause at the layer boundary
  (direct drive still has filament); encoder part `[filament_motion_sensor
  encoder_sensor]` = clog/tangle → immediate safe PAUSE (a clog cannot wait).
  `SET_FILAMENT_SENSOR` takes the SECTION name — the `switch_sensor` from the
  BTT example is INVALID if your section is named `filament_sensor` (it aborted
  the whole runout chain). PAUSE/RESUME/CANCEL also
  switch the encoder part (guarded) — the clog protection survives runouts.
- **Cold pull** (Maintenance > Filament): Heat-to (PLA ~240) / Pull-at (PLA ~100,
  PETG/ABS 120-140) → "1) Prep + PULL" heats, extrudes 25 mm, fan-cools → ALARM
  → pull in ONE firm motion → "2) Finish" verifies. Idle only.
- **Retraction test:** retract/unretract pairs at temperature to compare stringing

## 8. Temperature system L1/L2

- **Two temperatures per heater:** Layer 1 (L1) and from-layer-2 (L2).
  **One priority ladder for BOTH (.121): your override (ON) > file value >
  material preset** — what stands at each layer:
  - **L1**: the start paths heat to your L1 override if armed, else the file's
    own first-layer value, else the material preset (when L1 rules are ON).
  - **L2**: at the layer-2 boundary the system switches to your L2 override
    if armed, else the file's own layer-2 value (from its M104/M140 or the
    file info), else the material preset — **in BOTH start modes**, marked
    files (LAYER_MARK) and unmarked ones (Z tracker) alike. Generated and
    range files (no own M104/M140) switch through the material preset too —
    the bed no longer stays at its layer-1 value (field fix .121).
- purge + layer 1 = L1 (the start paths heat the hotend to the L1 value for the purge)
- **Interceptors (.121):** file M104/M109/M140/M190 are handled BY LAYER —
  - **AS LEGACY**: layer 1 → L1 value; layer ≥ 2 → your armed L2 override
    rewrites the command, otherwise the file's own value passes unchanged.
  - **AS SLICED**: layer 1 → the first-layer rules (material preset) shape it,
    your armed override wins if set; layer ≥ 2 → truly 1:1 (the file's own
    command stands) — except your armed L2 override, which still wins
    (`M104: 215C -> YOUR L2 override -> 240C (AS SLICED, layer 2)`).
  - Every rewrite is idempotent (only written when the target really moves
    > 0.5 °C) and logged once on the console.
- layer 2 = L2 — switched by LAYER_MARK (marked) or the Z tracker (legacy / AS
  LEGACY), identical values; the held layer-1 fan comes back at the boundary
  (`M106 S<file value>`) and your material fan scale re-applies
- sequential: every object restarts with L1
- live temps: `SET_LIVE_HOTEND_TEMP T=` / `SET_LIVE_BED_TEMP T=`
- idle filament handling heats to ≥200 °C (or preset)

**Safety:** heaters off at print end + on shutdown/cancel; pauses keep targets on
purpose; hotend fan cool-down (cooldown_fan_time, 30 s default).

## 9. Speed, acceleration & machine limits

**First-layer speed (default 75%, 0 = off)**

- global M220 brake during layer 1 — set at the start, re-applied after EVERY
  resume (Klipper restores the speed factor from pause time — that back door is
  closed) and at every object change
- the file's own M220 commands are capped to the limit while layer 1 runs
- AS SLICED: not applied · restored at layer 2 (marker or Z-tracked)

**Global = the ONE overall regulator (R92.1 model, all three parameters):**

- **Speed:** global % (LCD, L1 brake, file M220) scales everything — stored
  clean as `g_speed_clean`, never multiplied by anything else. Feature speed
  = percent **x global** (global 80 + wall 80 -> wall runs at 64, the next
  feature is back at 80 — no decay). Example: feature base 60 mm/s, feature
  200% -> 120; global 150% -> 180 mm/s, feature stays 200%.
- **Flow:** the exact same shape. Global flow (SET_FLOW_RATE / pre-print
  override) is the one regulator; a feature flow % always **refers to the
  global**: global 98% x feature 110% = 107.8% effective. Raising the global
  raises every feature's effective flow with it — the feature percentages
  themselves never move. (R92.1 fix: feature flow used to REPLACE the global
  instead of multiplying with it.)
- **Accel:** feature values are **hard limits** (absolute mm/s²) — the global
  accel never overrides them; it rules everything without its own feature
  accel (travel/unknown). ON TOP of that there is ONE global percent scaler
  (`Feat x%`, `SET_GLOBAL_ACCEL_PERCENT PERCENT=150`) that scales ALL feature
  limits in the same ratio (1500 at 150%) without touching the global accel —
  Live Tuning > Acc per feat shows the current feature's effective value live
  (`Eff: 1500mm/s2`), and Live Tuning > Extrusion > Flow sources shows the flow model.

Two rules keep it intuitive when BOTH are set: every global change re-applies
the running feature on the spot (global 100 -> 150 with wall at 200% moves
the wall from 200 to 300%, not back to 150), and a feature with its own accel
KEEPS it — the global accel rules everything that prints without one.

**Why the redesign (field log):** the old
APPLY_TYPE ran through the M220 interceptor — 75% brake x 80% wall multiplied
on the ALREADY scaled factor, feature by feature: 75x80 -> 60 -> 48 -> ... ->
19%. Since then feature values go straight to Klipper via the BASE commands
(M99220/M99221/M99204) — the interceptor (and with it the global value) is
never touched by a feature.

**16 features:** outer/inner wall, overhang wall, sparse/solid infill,
top/bottom surface, bridge, internal bridge, gap fill, support, ironing
(+own flow), skirt, brim, prime tower, custom code — every one with its OWN
ON switch + speed % + accel (Pre-Print > Features, one submenu each; Live
Tuning shows the CURRENTLY printing feature as "Cur:" — or "CurOv:" to
toggle its override live). Post-processor v4 maps every slicer family's
;TYPE: spellings (census table in ch. 3) — since R95 including Overhang
perimeter, Internal bridge, Prime/Wipe tower and custom G-code sections.

**Originals, availability & OFF-reset:** the post-processor MEASURES the
real values from the g-code itself — the most frequent F value per feature
segment (= its speed in mm/s) and the M204 in effect there (= its accel).
They are shown everywhere (the "File:" rows in Spd/Acc/PA per feat)
and they are what "OFF" returns to: switching a feature override OFF resets
the stored speed to 100% (= 1:1 with the file × global) and the stored accel
to the file's M204 (0 if the file sends none). Only features that really
occur in the file are editable — the activator rows of absent features show
"n/a" and every input refuses with "not in this file" (unknown/legacy files
without TYPES data stay fully editable as before).

**Machine limits**

| Parameter | Override (Pre-Print > Velocity) | Live command | Klipper setting |
|---|---|---|---|
| Max acceleration | accel (ON + value) | SET_GLOBAL_ACCEL | max_accel |
| Max velocity | velocity (ON + value) | SET_LIVE_VELOCITY | max_velocity |
| Minimum cruise ratio | min_cruise (ON + value) | SET_LIVE_MINIMUM_CRUISE_RATIO | minimum_cruise_ratio (replaced a2d) |
| Square corner velocity | square_corner (ON + value) | SET_LIVE_SQUARE_CORNER | square_corner_velocity |

Overrides apply at print start ONLY when ON + value > 0 — everything OFF means
Klipper's [printer] limits and the file rule untouched (no forced 4000 anywhere).

## 10. Calibration — the ladder to good prints

Calibration only works in the right order: every step builds on the ones
before it (flow measured with a wrong E-step or unshaped motion is simply
wrong). The Maintenance menu on the LCD follows this ladder top to bottom —
walk it in menu order and you walk it correctly.

```
ONCE PER PRINTER                     PER MATERIAL
────────────────                     ───────────
1. PID tuning          ──┐           6. temperature tower
2. leveling (Z offset)  ─┼─ layer 1  7. pressure advance (+ smooth time)
3. bed mesh check       ─┘ looks right8. flow (extrusion multiplier)
4. extruder steps       ──┐          9. retraction
5. input shaper         ──┴─ motion  10. bridging
   is honest                        11. ironing card
```

### 10.1 PID tuning (Maintenance > PID Tuning)

First — everything temperature-dependent needs stable heaters. Hotend at
print temp WITH the part fan % it will actually run (own submenu), then bed.
`TUNE_PID HEATER=extruder TARGET=215 FAN=100` / `TUNE_PID HEATER=heater_bed TARGET=60` (FAN = the % the part fan will run at).

### 10.2 Leveling (Maintenance > Leveling)

Probe Z offset by the paper method: TESTZ ±0.04/±0.12, accept → SAVE_CONFIG.
Bed screws: turn per the console report (screws_tilt_adjust). This is what
makes layer 1 look right — do it before any material calibration.

### 10.3 Bed mesh (Maintenance > Bed Mesh)

A fresh adaptive mesh runs at EVERY print start (at bed temp, over the real
objects). Here you set: Mesh ON/AUTO/OFF, adaptive, travel cap while meshing,
save/load profiles. A mesh check print (Leveling) shows how the first layer
sits — details in ch. 6.

### 10.4 Extruder steps (Maintenance > Extruder Cal.)

Mark 120 mm → extrude 100 → enter what is left → the calculator sets the
rotation distance. Do this BEFORE flow and PA — both assume the extruder
moves exactly what it is told.

### 10.5 Input shaper (Maintenance > Vibration Cal.)

The motion foundation — PA and flow tests at speed are meaningless with
resonances in the data.

1. **Calibrate X / Y / X+Y** (`CALIBRATE_SHAPER AXIS=…`, frequency range and
   max smoothing editable) — the accelerometer records, Klipper recommends.
2. **Diagram (print) / (plot)** (`RESONANCE_DIAGRAM MODE=PRINT/PLOT`): builds
   a plate (or pen plot) per axis with the PSD curve, all 5 shaper response
   curves, the peak marker with Hz and the SHAPER TABLE (shaper / freq /
   remaining vibrations / smoothing) — the recommended shaper is boxed and
   marked OK. The print runs through the NORMAL start procedure.
3. **Apply result > X/Y > shaper** — the stored frequency of that shaper is
   applied, SET_INPUT_SHAPER runs live AND is saved as the boot override
   (survives every restart, printer.cfg untouched). No math, just pick.
4. Console: `SHAPER_RESULT` (table), `SHAPER_RESULT AXIS=X TYPE=MZV`,
   `… TYPE=EI FREQ=58` (manual fine tuning). The fit is a faithful port of
   Klipper's shaper_calibrate (ZV/MZV/EI/2HUMP/3HUMP).
5. Recalibrate after mechanical changes (the status line at the top of the
   menu shows the active shapers + frequencies).

### 10.6 Temperature tower (Maintenance > Temp Tower)

Per material, FIRST — the right temperature is the base for PA, flow and
retraction. Two ways:

- **Band control on a sliced tower:** Start/End/Step/Band adjustable, "Plan
  (calc)" shows the band plan, "Start tower" changes the hotend temp every
  BAND layers (works with marked AND legacy files), "Stop tower" ends it.
- **Generated standalone tower ("Print tower"):** no sliced file needed —
  blocks × BLOCK_HEIGHT, one temperature per block (SET_HEATER_TEMPERATURE, so
  no interceptor interferes), fan %, mesh + prime included. "Best" → the
  block's temperature becomes the hotend override (L1+L2, ON).

### 10.7 Pressure advance (Maintenance > PA Cal.)

The Orca-style line test, generated on the printer: all parameters editable
(temp/bed/start/step/lines/len/slow/fast/accel/layer/spacing + velocity,
cruise ratio, corner, retraction len/spd/unretract, flow — synced with
Pre-Print/Live Tuning), mesh first. Read the best line → "Best line" sets the
PA override. Babystepping stays available.

**PA Smooth Cal.** (own submenu): PA prefilled + editable, smooth time
0.020–0.200 s in 0.010 steps (19 lines) — "Best line" → smooth override ON.
Both calibrations run with YOUR motion parameters.

### 10.8 Flow (Maintenance > Flow Cal.)

"Print cube" GENERATES the single-wall cube — SIZE/HEIGHT/LAYER/FLOW% in the
menu, FLOW% baked into E (independent of the flow override), mesh + prime +
your motion values included. Then: measure the wall, Wall: value GO →
suggested flow % → Apply flow (override ON).

### 10.9 Retraction (Maintenance > Retract Tower)

GENERATED two-mast tower: the retract length rises block by block
(slicer-style `G1 E-` retracts — exactly what the slicer sends). Params:
START/STEP/BLOCK/BLOCKS/DIST (mast distance)/TOWER (mast size)/
RETRACT_SPEED/LAYER/SPEED/TRAVEL_SPEED + temps; mesh + prime included.
"Best" → the block's retract length becomes the retract override (ON).

### 10.10 Bridging (Maintenance > Bridging)

GENERATED test: LEN (long span, default 160 mm), SHORT % (10–50 % of it),
tower heights, tower size, bridge layers, bridge speed, bridge fan %.
"> Create file" builds `Bridge_<len>mm_<pct>pct.gcode`: two tall towers
diagonally across the bed with the long bridge on top, plus one additional
SHORT span at SHORT % hanging clearly BELOW the long bridge on its own lower
tower — inspect both sags from the side. Normal start procedure, every tower
+ bridge is an exclude object. All bridging parameters are live: Live Tuning >
Features > BRIDGE (speed %), fan, flow.

### 10.11 Ironing card (Maintenance > Ironing Cal.)

CARDS cards (1–6, sizes auto-fit), each on BASE base layers — ironing starts
on layer BASE+1 (BASE 4 = ironing only after 4 solid layers, like a real top
surface). Each card = one flow%/speed pair (default F10/S20 … F20/S40; cards
4–6 via console F4/S4…F6/S6). Mesh + prime included. "Best" → ironing speed +
flow overrides ON.

### 10.12 The per-material recipe

1) temperature tower → 2) pressure advance → 3) PA smooth time → 4) flow →
5) retraction → 6) bridging → 7) ironing card → **Save as preset**
(Pre-Print > Material — a preset stores pa_smooth + unretract speed too).
Print a small model of the material's real use case between steps; the
generators make that cheap (a flow cube, a 30-layer range of a known file).

## 11. Bed mesh & KAMP

**The mesh strategy in one line:** a fresh, adaptive, at-temperature mesh at
every print start — never a stale saved one.

**What runs at print start (AS LEGACY, or marked files with mesh ON):**

1. bed heats to target first (mesh at temperature, not cold)
2. the mesh calibrates ADAPTIVELY over the real print area — with
   `EXCLUDE_OBJECT_DEFINE` data in the file, KAMP's adaptive meshing bounds
   the mesh to the objects (plus `adaptive_margin`, default 5 mm); without
   object data the full bed is meshed (console: "No objects detected! …
   Defaulting to regular meshing")
3. "Old files" ON: legacy files get the mesh too; OFF: homing → heat → purge
   → overrides only
4. Travel cap (Pre-Print > Bed Mesh): limits the speed WHILE meshing (default
   off) — a courtesy for the mechanics, the mesh quality does not depend on it

**Menu: Pre-Print > Bed Mesh / Maintenance > Bed Mesh** — Mesh ON/AUTO/OFF ·
Save after · Adaptive · Travel cap · Calibrate now · Load…/Delete… (profiles).
"Save after" stores the mesh as a profile at print end — useful if you
deliberately want to reuse one (e.g. for repeated small parts).

**KAMP settings (Maintenance > KAMP)** — the menu shows active/missing:

| Entry | Effect |
|---|---|
| KAMP mesh: ON / native | ON = adaptive meshing over the objects; native = Klipper's own full-bed mesh |
| KAMP purge: ON/OFF | replaces the own purge line with KAMP's |
| > LINE purge / > VORON purge | KAMP's line or the Voron-logo purge |
| Smart Park: ON/OFF | parks the nozzle inside the mesh area, warmed, instead of the corner |

**KAMP purge vs the own line:** KAMP's LINE purge is NOT probe-offset aware —
with a side probe offset > 10 mm it is skipped automatically (console says so)
and the probe-safe own line (ch. 6) runs instead.

**Adaptive mesh and exclude_object:** the object list is rebuilt at every
file OPEN (Klipper clears it) — skipped objects leave the mesh bounds cleanly
during a running print; the mesh stays as it was calibrated at start.

## 12. Purge / prime line

The prime line is what makes layer 1 clean: a wiped nozzle, a refilled molten
pocket and a fat line that proves flow before the part starts.

**The chain (every purge, own line and KAMP line/logo):**

1. **Nozzle wipe first** (`_NOZZLE_WIPE`): heat to 180 °C if the nozzle is
   cold, fast zigzag on the front-left silicone pad (X0–13 / Y0–13, max 4 mm
   down, 2 passes), then the nozzle parks HIGH again before the line is drawn.
   CLEAN_NOZZLE (Maintenance) does the same standalone; called cold it turns
   the heater back off afterwards.
2. **Flush 6 mm** (E F150) after a 3 s heat soak — refills the molten pocket
3. **Fat line** up to 110 mm, 1.2 mm wide (E from layer height) at F1200 —
   wipes the nozzle
4. **Retract −2.5 mm** — no blob on the first perimeter

The part fan is switched OFF after every purge — a cool-down fan from the
PREVIOUS print (PRINT_END runs it 100 % for 30 s) can no longer bleed into
the new first layer.

**Probe-safe geometry:** the line runs along X, STARTS at the RIGHT end and
is drawn toward x=0; Y only ever increases. The [probe] x_offset/y_offset is
respected — nozzle AND probe stay inside the bed with a 5 mm margin, so a
side-mounted probe can no longer slam into the bed frame. Placement: the
option with the LONGEST line wins — front strip 10 mm below the objects, left
of them, or right of them. `_PROBE_STOW` runs first — BLTouch/CR-Touch need
nothing, Klicky/Euclid users uncomment their DOCK_PROBE there.

**Edit spots:** 08 `_PRIME_LINE` (flush, width, length, margin) +
`_PROBE_STOW` (dock hook).

KAMP purge (LINE/VORON) replaces the line when enabled — see ch. 6.

## 13. Maintenance & care

The care side of the Maintenance menu — after the calibration ladder (ch. 9)
follow the care entries top to bottom.

**Clean Nozzle** — heats to 180 °C, zigzag wipe on the silicone pad
(X0–13/Y0–13 at max Z4, 2 passes), parks high. Runs in EVERY purge chain
automatically; standalone here for between prints.

**Filament** — load / load length / unload / unload length / change (M600);
also available before the print in Pre-Print. **Cold pull** lives here
(Maintenance > Filament): heats, pulls the filament cold to drag dirt out of
the nozzle — the classic fix for partial clogs and stringing after a material
change. Sequence: heat to the material's pull temp, advance fresh filament,
cool below the softening point, pull.

**Z Gantry Sync / Z Tilt** — the menu shows exactly what THIS printer has:
ONE Z stepper (or parallel-wired motors on one driver) → **Z Gantry Sync**
re-syncs both Z motors to a common zero (SET_KINEMATIC POSITION via
[force_move]); 2+ Z steppers → **Z Tilt** runs Klipper's Z_TILT_ADJUST over
the [z_tilt] probe points instead. Both have toggles for boot and print
start, Z Tilt additionally retries (0–5) and retry tolerance (0.005–0.2 mm)
— Maintenance > Z Tilt. Run either after mechanical work on the gantry or
when the X gantry visibly tilts. Z_TILT refuses politely (with a setup hint)
when [z_tilt] is missing from printer.cfg.

**KAMP** — mesh/purge/smart-park settings (ch. 6).

**Tests** — LED demo, sound demo, self test, status: verify actuators after
wiring changes without heating anything.

**Regular checks (recommended rhythm)**

| When | What |
|---|---|
| every print | glance at layer 1 (purge line + first perimeter tell the whole story) |
| weekly / after ~1 kg | clean the nozzle, cold pull if stringing increases, check the bed for residue |
| monthly | belt tension (ping test), V-roller play, PTFE tube seat at the hotend, screws on the gantry |
| after any mechanical change | re-run the calibration ladder from step 5 (input shaper) — and steps 1–2 if the hotend or bed moved |
| after a heater/fan change | PID tuning again |

## 14. LCD menu reference

Seven top groups — in LCD order: **Start Print?** (appears in the waiting
state, position 1), **Live Tuning** (during a print, position 2), then
Pre-Print, Quick Macros, **Tools** (the six part generators:
Cable ties · Angles+Flat · Lithophane · ColorPic · Gaskets · Labels ·
Bricks (catalog, kit, figures) · Plotter, each with its own sub-menu — plus **After gen** (QUEUE/PREVIEW, .84): what
happens to every generated file, see 5.0),
Maintenance, System. Klipper's own stock menus OctoPrint, Temperature and
Setup are hidden (.104) — everything they do exists in the R2 menus; the
SD Card browser, Control and Tune stay. Start dialog and live tuning sit right at the top. Every line fits the 16 characters
of the 12864 display — the value you edit is always visible (test-enforced).
Pattern: first line = ON/OFF toggle (value stays stored), then the values.

**Live Tuning (during a print, every mode)** — shows Klipper's REAL values:
the flow input reads the actual extrude factor (M221), PA reads
`pressure_advance`, smooth reads `smooth_time`, accel reads `max_accel`,
retraction reads the firmware values — what you see is what runs.

| Entry | Contents |
|---|---|
| Z +0.04 / +0.12 / −0.04 / −0.12 | babystepping right at the top |
| Hot / Bed / Fan / Zoff | cockpit: temperatures, fan %, Z-offset display · fan clamp: Clamp ON/OFF, FMin, FMax, FBrdg (bridge boost %, 0 = off) — every M106 of the file runs inside the curve (.85) |
| Spd per feat (.104) | Glob % (THE overall regulator) + FeatSpd: the currently printing feature's % + FeatOn: its ON switch + Src info (file/overwrite/live) + "Now:" which feature is printing + all 16 feature % rows (TRV = travels) |
| Acc per feat (.104) | global mm/s² + Feat x: scales every feature accel by % + the effective accel + FeatAcc: the currently printing feature's accel + all 16 feature accel rows |
| PA per feat (.104) | Glob: the global PA + all 16 feature PA rows (input shaper PA lives per feature) |
| Flw per feat (.104) | Glob: the global flow % + all 16 feature flow rows (ironing flow in its own feature menu) |
| Features | 16 submenus = same as Pre-Print > Features, but live: edits re-apply immediately when that feature is printing · ShpOff: input shaper OFF for one feature (toggle, .85) — each feature submenu has its own PA input (feature pressure advance, .85) |
| File (G-code) | FULL mirror of the Pre-Print file info: measured originals (speed/accel per feature), 16 click-activators, temps, PA, retraction, fan, flow, MAXRATE (mm³/s) + seam position + DERIVED flag (.85) — everything during the print |
| Extrusion | Flow % (1–300), PA, PA smooth, RetLen / RetSpd / Unret, UnretExt, Ironing flow, **Z-Hop ON/OFF + height** (lifts over every retract — nozzle-crash protection) — every input shows what Klipper REALLY runs right now, Src info shows file/overwrite/live |
| Velocity | Velcap (max velocity — caps the fastest moves = travels) · Acccap (global accel cap, travels included) · MCR · corner — live, like Mainsail |
| Plotter | while plotting: pen speed %, pen Z ±0.05, X/Y ±0.5 shifts — appears ONLY while a plot file runs (.104) |
| Pause & Control | pause now / next layer / at layer / Stop@ (planned NORMAL end) / M600 / Filament (Load/Unload/Change while paused) / cancel (2×) |
| Objects | skip single objects (2× confirm) |
| Sources | PARAM_SOURCES: provenance of every parameter (ch. 14.1) |

**Pre-Print**

| Entry | Contents |
|---|---|
| Offset X/Y/Z (.104) | X / Y / Z ±0.1 mm + each a fine row ±0.05 mm (halved steps, realtime MOVE=1) — SET_GCODE_OFFSET, the first thing you reach | (type, material, layer height × layers, line widths, flow ratio, by-object, nozzle × wall loops, ALL speeds, accels, L1/L2 temps, PA, retraction) + **sliced by <slicer> for <firmware>** (volumetric files get a loud warning) — shown from the MOMENT you select the file; the per-feature values are MEASURED from the g-code — PLUS 16 activator rows (OW…BM + OH/IB/PT/CU): each shows the file's REAL speed + o:ON state (.107: ON also lists the non-neutral parameters — S speed, A accel, F flow, P PA); CLICK toggles that feature's override; features NOT in the file show 'n/a' and refuse · Flow line: MAXRATE + seam + *derived* marker (.85) · Cap (mm³/s) + Fix flow cap · TAcc + Fix travel accel (.85) |
| Material | LOAD NOW + all material values + Save as preset — editing a value of the ACTIVE material applies LIVE too |
| Profiles | Material (Load/Save/Reset PLA/PETG/TPU + ABS/ASA) · Defaults (Save/Info/Load 1–8/Delete 1–8) · This file (Save pre/Load pre/Load post/Del pre/Del post — only existing slots appear) + Auto-load toggle (.84) · From optimized (pick a copy → values become the Pre-Print starting point, .128) |
| Temperatures | Bed L1/L2, Hotend L1/L2, Fan L2 (ON/OFF each) + File H:/File B: = the file's own values |
| Velocity (.104) | retraction len/spd/unretract + File R: · **Drive: DIRECT/BOWDEN (swap)** (.107 — the retraction starting-point profile, every value stays free) · Accel + Vel + MCR + Corner (ON/OFF each; Accel/Vel are GLOBAL caps — travels included; the LIVE accel caps but never RAISES a slower file value, .126) · Z-Hop ON/OFF + height — global PA moved to PA per feat. **.126: retraction overrides apply IMMEDIATELY and at every print start** — generated files retract via G10/G11 and never send a SET_RETRACTION the old redirect could catch |
| Features | 16 submenus: outer/inner wall, overhang wall, sparse/solid infill, top/bottom surface, bridge, internal bridge, gap fill, support, ironing (+flow), skirt, brim, prime tower, custom code — each shows the file's ORIGINAL (File:) + own ON switch + speed % (× global) + accel; only features the file really contains are editable — **a feature the file does not contain disappears from the menu entirely, an available-but-inactive one stays visible for live activation** (.83); switching OFF resets the stored values to the file original — never touches the global values · PA input per feature + ShpOff toggle at the top (.85) |
| Spd/Acc/PA/Flw per feat (.104) | four quick lists with the globals merged in: 1st-layer speed % (0 = off, default 75) · global accel + ON · global PA + smooth + File PA · global flow + ON · Now: the active feature — the former top-level Speeds/Accels/Flow menus, one level deeper but with everything in ONE place each |
| Bed Mesh | Level old files · Mesh ON/AUTO/OFF · Save after · Adaptive · Travel cap · Calibrate now · Load…/Delete… |
| Range/Stop | Stop@ layer + From/To (capped to the selected file's layer count!) + Floor/Top (each FOOTPRINT or OUTLINE, each GRID or SOLID fill) + Brim + Create excerpt (ch. C.1) |
| Filament | Load / Load length / Unload / Unload length / Change (M600) — available BEFORE the print too |
| File fixes (in File menu) | **Ret:** verdict line (FIX!/can/fixed/fw, .86) · RetFix ON/OFF (.104: now here) — auto-treats every NEW upload's clean retract pairs into G10/G11 (old Bowden-era files) · RetFix file (offered only for fix/can) + Vol->mm fix + Fix flow cap (Cap value) + Fix travel accel (TAcc value) — repair the SELECTED file directly on disk (start beep + done beep, markers survive) |
| Plotter (.104) | only when a plot file is selected: PEN FILE · pen speed % · Pen Z · Shift X/Y · Reset overrides — at the very END of Pre-Print |
| Texture | acts on the SELECTED file: File (shows the target) · Mode OFF/Fuzzy/Bumps · Fuz thick (0.05–1.5) · Fuz dens · **Presets (ORCA/Hide layers/Subtle/Grip)** · Pattern Grid/Waves/Honeycomb/Mandelbrot · Scale · Amp · Dir IN/OUT · > Apply (beeps) · How it works — writes a NEW `_TX` file (ch. 5.9), never auto-starts |

**Labels** (in Tools)

| Entry | Contents |
|---|---|
| Text | L1–L5 pickers · Show text · Pos 1–12 (cursor) · Chr (rotates A–Z a–z 0–9 space ÄÖÜäöüß and symbols) · Delete char · Clear text — the current text appears on the LCD with the cursor position; Fit gives a rough estimate, the exact preview follows ~2 s later |
| Settings | W/H (label size, default 50×15) · Font: SMOOTH / MONO / COND / NARROW / CAPS (the * marks the active one) · Lines 1–3 · Size (0 = auto) · Spc letter spacing · Stroke = letter line width (0 = auto, 0.6 = nozzle) · Base/Text layers · LH / 1st · Ironing · Hole NONE/LEFT/RIGHT/TOP/BOTTOM · Hole D · Brim · 2 colors · Gap (grid spacing) |
| Job | Queue n/24 · Add label · Del last · Clear all (2×) · Create (press 2×) · Fit (how many fit the bed) · How it works |
| Settings | W/H · Lines 1–5 · Size (auto or cap mm) · Spc · Base/Text layers · LH/1st · Ironing · Hole · Stroke · **Preview fit?** (real numbers incl. growth + minimum size for a fixed font) |

**Plotter** (in Tools) — DRAW/DOTS, dot gap, pen offset X/Y/Z, scale X/Y %,
bed corner limits, extruder ON/OFF, Z up/down, speeds, max size, auto-
contrast, Invert AUTO/ON/OFF, Drive frame test, Start (overrides), Plot text
file, > Plot status. All baked into the file at conversion time; live entries
while plotting (ch. C.3).

**Cable ties** (in Tools — ch. 5.4)

| Entry | Contents |
|---|---|
| Info | every setting in one console listing + material tip |
| Settings | Count 1–24 · Len 50–300 mm · Width 2–12 mm · Layers 3–6 (strap thickness) · LH 0.12–0.32 (finer = smoother teeth) · Closure: CLASSIC (one-way pawl, `*` marks active) / LOOP (adjustable bead loop, reusable) · Brim ON/OFF |
| Create (press 2×) | validates, bumps the job counter — the watcher builds the file in the background, it beeps + auto-selects |
| How it works | the flow + PETG/TPU tip + the Mainsail one-liner, right on the LCD |

**Angles+Flat** (angles + flat connectors, in Tools — ch. 5.5)

| Entry | Contents |
|---|---|
| Info | every setting in one console listing + the auto-hole rules |
| Mode | Angle (L) / Flat splice — the `*` marks the active mode |
| Settings | Angle 30–170° (**hidden in Flat mode**) · Leg A/B 20–150 mm (renamed Left/Right in Flat mode) · Width 8–60 · Layers 4–12 · LH · Holes 0–6 per leg · Hole D 2–10 mm (auto-clamped to the leg width) · Holes: Countersunk/Normal · Rib None/Gusset/Stepped (**hidden in Flat mode**) · Count 1–12  Walls 1-6 · Infill 20-100% · Ironing on/off |
| Create (press 2×) | validates, bumps the job counter — ready in ~1–2 s with the full adjustment report |

**Lithophane** (picture → back-lit relief, in Tools — ch. 5.6)

| Entry | Contents |
|---|---|
| Info | every setting + how many images are ready |
| Images (Create) | the gcodes folder's `.png/.jpg` list (newest first, 10 slots; plotter uploads included) — slot press = Create |
| Delete image | same slots, **2-press confirm** (press, press again) — only the image goes away, its plotter `.gcode` stays |
| Settings | Orient STANDING/FLAT · Height (Size in FLAT) 30–200 mm · Layer 0.08–0.2 (0.12 default) · Levels 0–12 (0 = photo, 2–12 posterized) · Colors 1–4 + ColL 1–30 (FLAT color bands) · Frame ON/OFF · Brim 0–10 · Ironing ON/OFF |
| How it works | upload, slot press, standing print, white PLA tip, Mainsail one-liner |

**Gaskets** (in Tools — ch. 5.7)

| Entry | Contents |
|---|---|
| Info | every setting + material tips |
| Settings | OD 12–200 mm · ID 6–190 mm · Height 0.4–6 mm · Face: FLAT / NUT (groove + two sealing lips, `*` marks active) · Ironing ON/OFF · LH 0.12–0.32 |
| Create (press 2×) | validates, bumps the job counter — the watcher builds the file, it beeps + auto-selects |
| How it works | spiral-per-band, NUT fallback rule, TPU/PETG tip, Mainsail one-liner |

**Frames** (picture frames / display cases, in Tools — ch. 5.8)

| Entry | Contents |
|---|---|
| Info | every setting in one console listing + closure explanation |
| Settings | Preset: Custom/9x13/10x15/13x18/A6 (`*` marks active; picking one fills W/H as editable values) · W + H 40–230 (custom, max follows the build volume) · Depth 3–60 mm · Border 4–30 mm · Corner r 0–30 mm · Walls 1–4 (loops per side) · Shape RECT/OVAL · Closure BACK/SIDE · Hang TOP/BOTTOM/LEFT/RIGHT/OFF · Stand ON/OFF · Surf: Ironed/Bed texture/Lines/Waves/Honeycomb (+ Depth/Spacing/Angle/Wave amp/Cell/Dir) · Disc: None/Glass/Plexi/Foil/Litho (+ Side/Thick) · Cable ON/OFF · Infill 20–100 % · **Presets: Save current / Load 1–8 / Delete 1–8** (your complete frame configs) |
| Create (press 2×) | validates, bumps the job counter — the watcher checks the bed fit and builds the file, it beeps + auto-selects |
| How it works | workflow, kit logic, snap-in/side assembly, Mainsail one-liner |

**Bricks** (building bricks / kits / figures, in Tools — ch. 5.10–5.12)

| Entry | Contents |
|---|---|
| Info | queue + settings + geometry summary |
| Catalog | all 45 codes (B/P/T × 1x1…8x8) — press bumps the count, same codes merge, max 120 parts |
| Settings | Layer 0.08–0.32 |
| Create | builds `V01_Bricks.gcode` from the queue (beeps + selects) |
| Kit from file | Source: the file SELECTED in the file list (or SRC=/INDEX= via Mainsail; nothing selected = clear error) · Detail: AUTO/MICRO 4.8/SMALL 9.6/BIG 3.2 · Mode: By plate (1 color/plate, zero M600) / By object (M600 at color boundaries) · Colors 1–8 · CREATE kit |
| Figures | Scale 25–300 % (5 % steps) · Count 1–24 · CREATE figure |

**ColorPic** (color pictures, in Tools — ch. 5.13)

| Entry | Contents |
|---|---|
| Images | the shared image list (newest first, 10 slots) — slot press = Create |
| Settings | Width 25–230 mm · Bands 2–8 · Band height 0.4–3 mm · Band colors (per-band palette picker, light→dark, auto ramp) · Layer 0.08–0.3 · Ironing ON/OFF · Brim 0–8 · Swap ON/OFF · Contrast ON/OFF · Vers |
| How it works | the band principle, M600 + LED blink, purge tower, Mainsail one-liner |

Dependency rules the menu enforces itself: Flat mode hides the Angle input
and the Rib submenu (a straight splice has neither), and the leg entries
rename to Left/Right so the halves are unambiguous. The hole count/diameter
never error out — the generator clamps and reports.

**Maintenance — in calibration order** (the ladder, ch. 9):

**PID Tuning** (hotend+fan% / bed) → **Leveling** (Z offset, bed screws) →
**Bed Mesh** (settings + profiles) → **Extruder Cal.** (E-steps) →
**Vibration Cal.** (shaper calibration, diagram print/plot, apply result) →
**Temp Tower** (band control + generated tower) → **PA Cal.** (line test +
**PA Smooth Cal.**) → **Flow Cal.** (generated cube + calculator) →
**Retract Tower** (generated) → **Bridging** (generated) → **Ironing Cal.**
(cards) → **Clean Nozzle** → **Filament** (load/unload/cold pull) →
**Z Gantry Sync / Z Tilt** (whichever this printer has) → **KAMP** →
**Tests** (LED/sound/self test/status).

**Macros (Quick Macros):** load/unload, gantry sync / z tilt, status, sounds on/off,
LEDs on/off, Nozzle LED — mode AUTO/ON/OFF + live brightness + live color
R/G/B + presets.

**System:** File check (+ Retag old 2×), restarts (2×), Pi shutdown (2×), **Force end print**, save config
(2×, warns that the LCD goes dark), status, **LED Setup** (areas, bed light,
nozzle chain/mode — ch. 17, only shown when LED hardware exists).

## 15. Overrides reference

Every override = value + OWN ON switch. SET_OVERRIDE_VALUE sets + ON ·
TOGGLE_OVERRIDE flips · CLEAR_OVERRIDES switches all off (values stay).
Naming: the console/LCD/Mainsail descriptions say **"Overwrite(s)"** (since
.31, your wording); the macro + variable names keep "override"
(SET_OVERRIDE_VALUE, ov_*) so existing buttons/scripts never break.

| Group | Keys | Defaults | Applied |
|---|---|---|---|
| Temps | bed, bed_after, hotend_first, hotend_after | 60/55 · 225/210 e.g. | start + intercepted M104/109/140/190 (by layer) |
| PA | pa, pa_smooth | 0.05 · 0.04 | from purge on |
| Retraction | retract_len, retract_speed, unretract_speed | 0.75 · 35 · 35 | from purge on |
| Machine limits | accel, velocity, min_cruise, square_corner | 4000 · 300 · 0.5 · 5 (OFF) | start, ONLY ON + value > 0 |
| Flow / Fan | flow, fan | 100 · 100 | flow global (M221) · fan scaled from the START — the file's M106 S0 stays 0, everything else is scaled by your % |
| Per feature | feat_spd_<code> + feat_acc_<code> + feat_on_<code> for 16 codes (wallouter, wallinner, infillsparse, infillsolid, surfacetop, surfacebottom, bridge, gaps, support, ironing, skirt, brim, overhangperim, internalbridge, primetower, custom); ironing + ironing_flow | 100 · 0 each | only while that feature prints (APPLY_TYPE): speed = % x CLEAN global, accel absolute — the global value itself never changes; feat_on=0 RESETS the values to the file original; unavailable features refuse |

The interceptors remember what the FILE asked for — file_hotend_first/after,
file_bed/after, file_retract_len/speed, file_fan, file_flow, file_accel,
file_speed — shown as File H:/File B:/File R:/File F:/File Fl:/File A: hints.
M221 (flow factor), M204 (accel) and M220 (speed factor) are intercepted too:
your overwrites win when ON, otherwise the file value passes 1:1 (/.35).

## 16. Sound reference

20 tunes as frequency:ms:volume triples (M300-based). PLAY_SOUND NAME=… ·
TOGGLE_SOUNDS · TEST_SOUNDS plays them all (Maintenance > Tests).

| Group | Tunes |
|---|---|
| UI / dialogs | r2_click · r2_confirm · r2_notice · r2_question (start dialog, repeats) · r2_pause · r2_resume |
| Start stages | r2_start · r2_leveling · r2_heating · r2_hot · r2_printing · r2_leveled |
| Tuning | r2_pid · r2_leveling |
| Filament | r2_filament (repeats) · r2_alarm |
| Endings | r2_done · r2_sad · r2_error · r2_happy |

**Beep discipline during a print** *(R95)*: every beep blocks the firmware
for its whole duration — on an active print the standing filament oozes a
purge blob into the part (micro pause → stutter). While the print is ACTIVE
the confirmation and feedback tunes stay **silent**: r2_confirm, r2_click,
r2_happy (generator success), r2_heating/r2_hot (live temperature changes) —
the NeoPixel effects carry the feedback instead. Critical tunes ALWAYS play:
pause, filament change, dialogs/questions, alarms, errors — and after the
print everything is back to normal.

Volume lives inside the tune triples (0.05-0.5 duty). Edit/add tunes in
02_sounds.cfg — 0 Hz = a pure pause.

## 17. LED reference

| State | Pattern | When |
|---|---|---|
| idle | calm blue breathing | ready, heaters cold |
| boot | blue/white scanner | system start |
| waiting | blue/white blink | start dialog waits |
| heating | red/orange chase | heaters ramping |
| homing | fast cyan scanner | G28 running |
| leveling | magenta scanner eye | mesh/screws/offset |
| pid | blue/white blink | PID tuning |
| printing | slow blue breathing + nozzle light | file running (gently alive: a 4 s breathing at 5 fps costs ~1% of the serial budget — the old 24 fps animation was the .122 'Timer too close' shutdown, 75 of 100 queued messages LED data) |
| paused | yellow breathing | any pause |
| filament | cyan/white chase | load/change/runout |
| alarm | red/white strobe | errors, cold pull |
| finished | green/white twinkle | print done |

Effects come from the klipper-led_effect extension (12 states above); the frame
chain is [neopixel printer_leds] 1-4, the nozzle light is LED 5. TOGGLE_LEDS
switches the FRAME off/on (sounds keep playing). After a finished print the
green/white celebration runs for `led_finish_time` seconds (default 10) and then
returns to idle breathing BY ITSELF — it used to twinkle forever.

All effects run at 12 fps (.123, R163), EXCEPT printing: it breathes slowly at
5 fps (.125, R166) — the LEDs are decoration, the serial bus is not — every
animated frame is a neopixel transmission on the same wire the moves travel,
and a failed LED readback is resent. The old 24 fps print animation flooded the
bus (the .122 field log shutdown); 5 fps = 5 messages/s ≈ 1% of the budget, so
the printing state moves again without touching the headroom.

### Nozzle LED — its own switch | work light while printing / filament change (r2_nozzle_on) |
| ON | always on with YOUR color + brightness — tool light, stays available even with the frame LEDs OFF |
| OFF | never |

- LCD: **Quick Macros > Nozzle LED** — `> AUTO (print)` / `> ON` / `> OFF` (the
  active mode gets the `>` marker), live inputs `Bright: …%` (5-100),
  `Red/Green/Blue: …%` (0-100), presets White + Warm. Every change applies
  IMMEDIATELY — also mid-print.
- Console/Mainsail: `NOZZLE_LED` (status) · `NOZZLE_LED MODE=on|off|auto` ·
  `NOZZLE_LED BRIGHT=0.4` · `NOZZLE_LED R=1 G=0.85 B=0.6`. SHOW_STATUS lists the
  current values.
- POWER RULE: your color × brightness is hard-capped at 0.5 per channel — the
  board's neopixel port stays safe no matter what you dial in.

### LED areas — status / bed light / nozzle (R108)

One chain, three jobs — and the split is YOUR choice (the example from the
field: 3 status + 4 bed lighting + 1 nozzle). It lives in the **hardware
profile** `r2_hardware.cfg` (see ch. 19b) — the second variables file that
survives deleting `variables.cfg`:

| Area | LEDs | What it does |
|---|---|---|
| Status | 1 … `led_status_n` | the animated effects above (frame lighting) |
| Bed light | next `led_bed_n` | steady WHITE work light, own ON/OFF + brightness (0–0.5) |
| Nozzle | last of the chain — or its own chain (`led_nozzle_split=1`, e.g. EBB42 over CAN) | work light at the toolhead (see above) |

- **LCD: System > LED Setup** — info (LED_INFO: pin, chain, areas), master
  on/off, `Status LEDs` / `Bed LEDs` count inputs (hard-clamped to the real
  `chain_count`), bed light on/off + brightness %, nozzle main-chain/own-chain
  switch, nozzle mode cycle, hardware info.
- Console/Mainsail: `LED_INFO` · `SET_LED_LAYOUT STATUS=3 BED=4` ·
  `SET_BED_LIGHT STATE=1|0 TOGGLE=1 BRIGHT=0..0.5`.
- LCD edits apply **immediately** and persist into `r2_hardware.cfg` (via
  `[gcode_shell_command R2_PERSIST]` — setup.sh adds it when the shell-command
  extension is installed; without it the edit holds for the session).
- The animated `[led_effect]` ranges are static Klipper config — changing the
  status count regenerates them (`tools/r2_persist.sh`), one FIRMWARE_RESTART
  applies. Bed light + nozzle index are live right away.
- Other SET_LED-compatible chains work too: the wizard writes `[neopixel]` or
  `[dotstar]` (data + clock pin) sections — `led_type` + `led_section` tell the
  macros which one is yours.
- **Color order (.84):** the wizard asks the BYTE ORDER of every chain
  (GRB = WS2812/WS2815/SK6812 'Neopixel', RGB = WS2811 12 V strips,
  BGR = APA102/SK9822 'dotstar', RGBW = SK6812 with a real white chip, rare
  clones, or a per-LED comma list) — with the plain-English explanation that a
  wrong order SWAPS colors (red glows green) and breaks nothing. Unsure? Take
  the default, run the LED test (System > LED Setup) and re-run setup.sh if
  red and green are swapped. The chosen order is written into every generated
  `[neopixel]`/`[dotstar]` section and kept in the hardware profile; an
  existing user section is never edited (the wizard tells you what it says).

## 18. Console messages

`[OK]` success · `[i]` info · `[!]` warning · `!!` error. M117 mirrors the
essence onto the LCD. Typical lines you will meet:

```
M104: 215C -> OVERWRITE -> 225C (layer 1)
M104: 215C -> YOUR L2 override -> 240C (AS SLICED, layer 2)
M220 S100% capped to 65% (layer 1)
Layer 1: speed brake re-applied (65% after resume)
Layer 2: hotend -> 205C (your override · file value · material PLA · Z-track — whichever wins)
Layer 2: bed -> 55C (…) · Layer 2: fan back on (file value S200)
Sequential print: next object (NAME) - back to LAYER-1 temperatures
Temp tower: layer 21 -> 215C
Print running (legacy file) - live tuning and overwrites ACTIVE
=== PRINT RUNNING === / Print finished: NAME (duration)
```

## 19. System: Klipper & Pi

| Command | Effect |
|---|---|
| SYS_FIRMWARE_RESTART CONFIRM=1 | Klipper restart (macros reload) — 2× |
| SYS_HOST_RESTART CONFIRM=1 | host service restart — 2× |
| SYS_SHUTDOWN CONFIRM=1 | heaters/fans/LEDs off → Pi shutdown via moonraker |
| SYS_SAVE_CONFIG | guarded SAVE_CONFIG: refuses during a print, skips when nothing is pending, warns that the LCD goes DARK for up to 2 min before restarting (2×) |
| HOST_CHECK | **Pi health report**: throttle/undervoltage flags (now + since boot), CPU temp, load **vs. core count**, **RAM + swap**, disk, **iowait**, **TOP CPU/RAM processes (top 5)** and **who sits IN the swap** (VmSwap per process — names the RAM eater even when the top-RAM list looks innocent) + **service states** (klipper/moonraker/avahi/crowsnest/sonar/OctoEverywhere/pigpiod, with warnings: double webcam stack, avahi still on, cloud relay) — honest verdict: THROTTLED / SWAPPING / OVERLOADED / OK. The swap verdict measures **activity** (vmstat swap-in/out): quietly parked pages after boot are **OK** (normal on a small Pi), only real swap traffic counts as SWAPPING. LCD: System > Host check |
| EMERGENCY_STOP | immediate halt |
| FILE_CHECK | **g-code inventory**: scans every file's tag version — how many are current, old (upgradeable), untouched (never processed) or plotter files — each file listed on the console with age + size. `FILE_CHECK RETAG=1` (2×/CONFIRM=1) additionally upgrades old + untouched files to the current markers: **.r2bak backup first**, never while printing, max 20 per run. LCD: System > File check + STALE (v4: functional, pre-.86 info line — RETAG adds the new keys) |

All destructive paths need TWO presses (60 s window). Serial link: UART (ch. B.5).

**Why FILE_CHECK exists:** markers (`APPLY_TYPE`, extended `_FILE_INFO`,
measured per-feature speeds) grew over the versions — a file uploaded long
ago prints, but the newer features (feature overrides, live preview,
measured originals) stay blind to it. `FILE_CHECK` shows exactly which
files those are, `RETAG` brings them up to date without a re-upload. The
direct SSH variant (no Klipper needed):

```
python3 tools/r2_postproc.py --file-check ~/printer_data/gcodes
```

### 19a. The MCU-shutdown watchdog (.129 / R170)

**What you saw (.128 field report):** after an MCU shutdown the display
froze — and the heated bed seemed to stay ON until you pressed
FIRMWARE_RESTART. That felt dangerous, and you asked for proof + safety.

**How Klipper is built:** on an MCU shutdown klippy turns **every heater
OFF by design** — the host must confirm each heater activation every 3 s,
and the heater pins default to `shutdown_value: 0` with a max-duration
watchdog. That holds even when the host itself crashes. Your bed is 24 V DC
at the board — when klippy stops confirming, the MOSFET closes.

**What the watcher does now (your choices):** it polls klippy's state every
2 s. On `shutdown` it opens a **10-minute evidence window**: bed + hotend
temperatures (target vs. actual) land in
`logs/r2_shutdown_watchdog.log` every 5 s — if the bed curve DECAYS, power
was cut (proof in writing); if it ever HOLDS at target, power is flowing
and you have a wiring/SSR fault worth fixing. After **5 minutes** in
shutdown it sends the **FIRMWARE_RESTART itself** (max 2 per boot of the
watcher, at least 1 h apart — no restart loops). Every step is logged.

### 19b. setup.sh / update.sh — wizards, backups, change modes (R108)

**The hardware profile — a second variables file.** `r2_hardware.cfg` (next to
printer.cfg, included by one line) carries everything that makes THIS printer
tick: build volume (bed min/max X/Y, Z height), probe offsets, nozzle-clean
(wipe) + part-presentation positions, and the LED layout (ch. 17). It is
deliberately separate from `variables.cfg`: resetting your print settings
(deleting the normal variables file) can never lose machine compatibility —
and the LCD-editable hardware values (LED areas) persist into it. `HW_INFO`
(console / System > LED Setup > Hardware info) shows it at any time.

**The wizards.** `bash klipper-e3-r2d2/setup.sh` asks every hardware value in
English — each entry validated AND confirmed a second time (mistakes can be
corrected before anything is taken over), a summary + final confirmation
before the profile is written. The LED wizard asks: LEDs at all? neopixel or
dotstar, section name, pin (SKR mini E3: PA8 · EBB42 CAN: EBB:PD3), chain
length, color order, status/bed-light/nozzle areas, EBB split chain, bed
brightness. `update.sh` asks FIRST whether to **keep** the current LED +
hardware settings (default) or re-run the wizards — and re-applies the LED
layout to the freshly unpacked `03_leds.cfg` either way.

**Backup before anything.** Both scripts start by copying every file the run
might change (printer.cfg, moonraker.conf, KAMP_Settings.cfg,
r2_hardware.cfg, macros/03_leds.cfg, the service unit) into
`r2_backups/<timestamp>-setup|-update/` — and VERIFY each copy byte-identical
(`cmp`) before a single modification happens. A failed verify aborts the run.

**Every change is shown first — four ways to apply.** Nothing is ever silently
written into your printer.cfg / moonraker.conf:

| Mode | What happens |
|---|---|
| 1 — automatic | the lines are inserted (in printer.cfg always BEFORE the `#*#` block); your own conflicting lines are only COMMENTED OUT — never deleted |
| 2 — commented only | the lines go in commented (`# R2> `) — you remove the marker yourself when you want them |
| 3 — separate txt (default) | the lines land in `r2_manual_changes.txt` with target file + position — SAFEST: your files are not touched at all |
| 4 — skip | nothing |

**Object processing (moonraker).** Both wizards show the CURRENT state of
`enable_object_processing` and explain it: ON = moonraker analyses every
upload itself — files without slicer object data still get adaptive KAMP
meshes + the LCD Skip-Objects menu (fine on a strong host); OFF = recommended
on a Pi Zero 2 W / Pi 3 (the analysis costs RAM on every upload — with it off,
KAMP meshes full-bed on such files and the purge falls back to our own line).
Keep / turn on / turn off — the change goes through the four modes above.

## 20. Variables & editing the .cfg files

Persistent settings live in ~/printer_data/variables.cfg — change via LCD/console;
never edit the file while Klipper runs. Runtime state lives in _STATE (not persisted).

| Group (save_variables) | Keys |
|---|---|
| Material | material, mat_* (per-material presets) |
| Mesh | mesh_mode (ON/AUTO/OFF), mesh_always (fallback), mesh_adaptive, mesh_auto_save, mesh_last_profile, legacy_level |
| Print behavior | first_layer_speed (75), load_length (60), unload_length (90), pid_fan_percent |
| Overrides | all ov_* keys + ov_*_on switches (ch. 15) |
| PA calibration | pa_cal_* (temp, bed, start, step, lines, len, slow, fast, accel, layer, spacing) · smooth_test_start/step |
| Flow / tower / ironing | flow_cal_* · tt_start/end/step/band/active · iron_cal_temp |
| Cold pull / misc | cold_pull_hot, cold_pull_pull, cooldown_fan_time, heaters_off_at_end, motors_off_at_end |
| System | sound_on, leds_on, start_confirm, gantry_sync_*, kamp_*, ishaper_* |
| Nozzle LED | nozzle_mode (auto) · nozzle_bright (1.0) · nozzle_r/g/b (0.9/0.9/0.85) · led_finish_time (10 s finished celebration) |
| Hardware profile (r2_hardware.cfg — survives a variables.cfg reset!) | bed limits + Z height · probe_x/y · present_x/y · wipe_x/y · led_type/section/status_n/bed_n/bed_on/bed_bright/nozzle_split/nozzle_section |
| Generators / texture | *_nonce job counters · texture_mode/thick/density/pattern/scale/amp/dir · file_check_retag |

Nice edit spots per file:

| File | Edit spots |
|---|---|
| 05_materials.cfg | variable_presets — the shipped material defaults |
| 08_print_start_stop.cfg | _PRIME_LINE (flush 6 · width 1.2 · length 110 · margin 5 · direction right→x0) · _PROBE_STOW (dock hook: uncomment DOCK_PROBE for Klicky/Euclid) · waiting heights Z10/Z40 |
| 09_pause_filament.cfg | _PARK_HEAD (corner logic · lift 5 mm · anti-ooze −3 mm) |
| 12_maintenance.cfg | CALIBRATE_PA defaults · IRONING_CAL zones · TEMP_TOWER defaults |
| 02_sounds.cfg | tunes — triples freq:ms:volume |
| 03_leds.cfg | colors · patterns |
| 01_state.cfg | variable_version · INIT defaults |

```
Golden rules: single braces {…} (NEVER {{ }}) · {% … %} for logic · no {# #}
inline comments in gcode · SAVE_VARIABLE names lowercase · True/False capitalized
· keep rename_existing: lines (the M99xxx base commands live behind them!)
```

### Hints from the macro comments (user adjustments)

| Where | Hint (from the code) |
|---|---|
| 01 INIT | runs 5 s after boot, fills only MISSING keys — your saved values are never overwritten |
| 05 presets | variable_presets are shipped defaults; your saved mat_<material>_<key> values always win — "Save as preset" makes yours permanent |
| 06 overrides | override ON → temperature redirected to YOUR value; OFF → file value passes unchanged |
| 08 purge | purge ALWAYS (user rule) — hotend heats to the LAYER-1 temperature first |
| 08 probe | _PROBE_STOW hook runs before every purge — dock your Klicky/Euclid probe there |
| 08 dialog | AS LEGACY uses your selected material · AS SLICED takes the material from the file |
| 09 pause | idle timeout = infinite during a pause — Klipper must never turn heaters off mid-pause |
| 10 PA | with the PA override ON, a sliced-in SET_PRESSURE_ADVANCE cannot override your value |
| 11 gantry | Z motors wired in parallel on ONE driver — SYNC_GANTRY does the mechanical sync; watch the first run. A printer with 2+ Z steppers + [z_tilt] gets Z_TILT everywhere instead (LCD swaps automatically) |
| 12 screws | screw positions live in [screws_tilt_adjust] in printer.cfg → ADJUST TO YOUR PRINTER |
| 15 objects | console users can always use Klipper's native EXCLUDE_OBJECT as well |

## 21. What happens when a macro executes

### 21.1 The idea in one worked example — from upload to finished print

The system's purpose in one sentence: **the printer understands its files.**
Four building blocks make that work — reading files, tagging them,
recognizing features, and triggering functions. Here is the complete chain
for a real print (`vase.gcode`, sliced in OrcaSlicer for Klipper):

**1. Reading the file (the watcher).** A service on the Pi
(`tools/r2_postproc.py`) watches the gcodes folder. One second after
`vase.gcode` arrives it reads the WHOLE file once: layer comments, `;TYPE:`
feature comments, slicer header, object definitions, temperatures, speeds —
and writes what it learned into the file itself.

**2. Tagging.** The watcher inserts markers that Klipper macros can react to:

```
; R2-POSTPROC v4          ← the tag: "this file is processed" (never twice)
_FILE_INFO LAYERS=312 …   ← everything the preview shows, one block
LAYER_MARK               ← before every layer change
APPLY_TYPE TYPE=WALL-OUTER  ← after every ;TYPE: comment
```

**3. Feature recognition.** `_FILE_INFO` contains the MEASURED values per
feature (which speeds really are in the file), the layer count, by-object
mode, the slicer + firmware it was made for. The moment you SELECT the file,
this block replays into the system — Pre-Print > File info fills itself, the
start dialog knows what it is dealing with, volumetric Marlin files get
flagged.

**4. Triggering functions.** During the print, the markers fire macros:
`LAYER_MARK` counts layers (→ layer 2: L2 temps, file fan back, full speed),
`APPLY_TYPE` switches the live overrides to whatever feature is printing
right now, `PRINT_START`/`PRINT_END` (or their absence in a legacy file!)
trigger the start/end choreography. The file NAME is a trigger too:
`photo.png` selected in the file list switches to plot mode (the watcher
generates `00_Plot_*` on demand), `notes.txt` to a text plot —
and a saved variable bumping (the "nonce" counters) triggers the five
generators of chapter 5 in the background.

The same pattern everywhere: **detect once, decide in a macro, act live.**
Nothing is baked in — AS SLICED runs the file 1:1, and every automatic rule
is a switch you can turn off.

### 21.2 Execution mechanics

1. **Render before execute:** Klipper evaluates the whole template FIRST, then
   runs plain gcode — a macro cannot see values it just set. Verification phases
   run as delayed_gcode (_LEGACY_PREP2 1.5 s, _OBJECT_PREP 2 s) and render FRESH.
2. **rename_existing interception:** M104/M106/M140/M190/M204/M220/
   SET_PRESSURE_ADVANCE/SET_RETRACTION are OUR macros; the real commands live on
   as M99104 … M99220 and receive the redirected values.
3. **delayed_gcode** = "run once in N seconds". _STATE_WATCHER re-schedules every
   second; LED animation frames come from the led_effect extension.
4. **State lives twice:** fast runtime state in _STATE variables · persistent
   settings in save_variables.
5. **{action_…} calls** become host actions — the Pi shutdown is moonraker's method.
6. **Errors abort the chain** — risky sequences are split into phases: a hard
   error in phase 1 cannot kill phase 2; it just never runs. Look ABOVE in the
   console for the first real error.

## 22. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Must home axis first | the real error is usually ABOVE it in the console; right at a legacy file's start: fixed in .32 (START_PRINT does the real legacy start) |
| L1 speed did not apply (legacy) | file sent M220 S100 — capped + re-applied after every resume /.26 |
| L2 never came after object change/skip | .24 frozen-counter bug — fixed in .26 (Z re-anchors at every object start) |
| Purge moved but nothing came out | heat soak + tighter wait ; check tension/clog if still weak |
| Values "not applied" | override OFF or 0 (SHOW_STATUS) — or print runs AS SLICED |
| LCD value invisible while editing | fixed — all labels ≤16 chars incl. value (test-enforced) |
| Retraction LCD stale/reset | live mirror |
| Acceleration changed without asking | old forced 4000 — now only ON + value > 0 |
| Probe samples exceed tolerance | clean the bed; samples_tolerance: 0.15 |
| Unknown profile r2 after restart | mesh was session-only → "Save after print" ON |
| VARIABLE must not contain upper case | ancient version → upload complete package |
| LCD entries missing/mixed | old lcd_menues.cfg → upload complete folder |
| No sounds | [pwm_cycle_time beeper] missing/wrong · TOGGLE_SOUNDS |
| Pi shutdown does nothing | moonraker not reachable — SYS_SHUTDOWN logs clearly |
| Probe hit the bed edge at the purge line | fixed in .29 — prime line is probe-offset aware (right→x0); KAMP LINE purge auto-skipped with side offset > 10 mm |
| "Minimum cruise ratio not applied" | it IS passed (SET_VELOCITY_LIMIT, Klipper ≥ v0.12) — the console confirms: "[OK] minimum cruise ratio … -> Klipper" + "Machine limits -> Klipper: …" at start |
| SYNC_GANTRY needs force_move | [force_move] enable_force_move: True |
| KAMP meshes the whole bed | check KAMP_Settings.cfg margin |
| Dialog/menus "did nothing", mode stuck 'waiting' | .30 bug, fixed in .31 (dialog schedules its decision waiter, PRINT_START heals stale modes); dead watcher: .32 _WATCHDOG re-arms it every 5 s |
| "Extrude below minimum temp" at a legacy file's start | same .31 root cause + M109 no longer waits in the background; AS SLICED now homes, waits for the file's temps and purges before the file continues |
| Pause + L1 temps mid-object ("next object" from nowhere) | z-hop ratcheted the Z mark — fixed in: hops <= 1 mm are un-ratcheted, trigger zone tightened to < 0.75 mm |
| Hotend at full temp during bed + mesh (oozing) | the AS LEGACY prep drops it to 170C standby and re-heats for the purge |
| Movement file (no heating, no start gcode) runs cold / file ran during the start dialog | every print is caught — reliably (M25 holds the file at position 0, nothing runs before the decision); after the decision the net probe gives movement files home + heat (preset/overwrites) + purge automatically |
| 'switch_sensor' is not valid for SENSOR | SET_FILAMENT_SENSOR takes the SECTION name (filament_sensor / encoder_sensor) — the BTT example was copied 1:1 although your section is named differently; corrected block: ch. 7 |
| "Save config froze the printer" (LCD dark after Save config) | NOT a crash by design: SAVE_CONFIG restarts Klipper and the LCD keeps its last image until the MCU reconnects — on the Pi Zero 2 W that can take up to ~2 min (big config).: System > Save config warns first ("LCD goes dark"), refuses during prints, restarts anyway when nothing is pending (your R2 settings save instantly), and the boot beep + "R2 ready" confirm a SUCCESSFUL restart. Still dark + Mainsail error after 2 min → FIRMWARE_RESTART from Mainsail or `sudo service klipper restart`, then send ~/printer_data/logs/klippy.log (never power-cycle the Pi!) |
| Question came only after the bed heated | M190/M109 do not block while the decision is pending — bed preheats in background, question within seconds |
| Z_TILT refuses: no [z_tilt] section | add it to printer.cfg — one X,Y pair per Z stepper, e.g. `z_positions: 45,45` + `215,45`; single-driver printers don't need it (SYNC_GANTRY) |
| Nozzle preheats to 182 on select | that is the filament-swap level — change filament while the start dialog waits; Pre-Print > Preheat changes or disables it |
| **MCU 'Timer too close' shutdown** (host cannot feed the MCU) | ALWAYS a HOST problem — NEVER stepper current, never the electronics fan, never a safety trigger, and never a zip lying in the config folder (nothing scans it). **System > Host check** names it: THROTTLED = undervoltage (PSU/USB cable!) or heat · OVERLOADED = load >= core count, the Top-CPU list shows who — typical eaters on a Pi Zero 2: **webcam (crowsnest), sonar, OctoEverywhere, moonraker's object processing (enable_object_processing: True — your own moonraker.conf comment warns against it on a Pi Zero!)**, update manager, a fan/temp script with software PWM (RPi.GPIO) · SWAPPING = swap traffic RIGHT NOW (the check measures in/out — quietly parked pages after boot are OK and no reason to panic) — **the verdict names the processes sitting in the swap („Top SWAP") directly** · also: after boot/update give the Pi ~2 min before starting a print (moonraker + watcher both re-scan the whole gcode folder while klippy parses the big config). Software side already hardened: mesh travels capped, preview pushes cost zero disk writes, meshes run adaptive |
| Mesh is full bed although 'adaptive' |: honest wording — 'full bed (file has no object data)' now SAYS so. The mesh before a held file runs adaptive (the watcher replays the file's EXCLUDE_OBJECT_DEFINE at selection); Orca files carry them when 'Label objects' is enabled. Plot/label/bridge files bring their own object polygon |
| KAMP meshes the whole bed | check KAMP_Settings.cfg margin — AND the file needs object data (see row above) |

Diagnostics: SHOW_STATUS · SELF_TEST · KAMP_STATUS · HOST_CHECK (Pi health) · _CHECK_INSTALL at boot.

## 23. Limits & known behavior

- **nozzle diameter = printer.cfg truth**: every generator (labels, ties,
  angles, frames, litho, seals, bridge) reads `[extruder] nozzle_diameter`
  from printer.cfg — line widths, E-per-mm and hatch spacing all derive from
  it (fallback 0.6, console note when it deviates)
- texture tool: only outer-wall vertices move; the first outer vertex of a
  file and zero-length restarts stay untextured (no approach direction),
  a file without outer walls gets zero shifts — and the 100th version
  (V99 full) refuses with a cleanup hint instead of overwriting
- sequential detection needs the previous object ≥1.6 mm tall (protects by-layer prints)
- legacy files (no APPLY_TYPE): feature factors apply instantly, but only the
  GLOBAL factor is re-applied at layer 2 / after resumes
- "State re-synced" after object-change resumes: cosmetic self-healing
- AS SLICED = no injections, but homing/mesh/prime still run BEFORE the file
- temperature tower holds the last temperature at the end — stop it afterwards
- a2d/accel_to_decel no longer exists — minimum_cruise_ratio replaced it everywhere
- **the real bed is NOT position_max (R92):** the steppers' position_max is
  lifted on this machine (micro probe + mesh rides beyond the plate). All
  generators, the prime line and the park corners use the
  **[gcode_macro _R2_CONFIG]** settings macro in printer.cfg instead — without
  it everything falls back to the Ender-3 default 220×220 (x 0…220, y −3…217)
  and the console says so:

  ```
  [gcode_macro _R2_CONFIG]
  variable_bed_min_x: 0.0
  variable_bed_max_x: 220.0
  variable_bed_min_y: -3.0
  variable_bed_max_y: 217.0
  gcode:
      # config carrier only - never runs
  ```

  **Position options (R104, all optional — defaults = the classic behavior):**
  `variable_present_x: 10.0` / `variable_present_y: 228.0` — where PRINT_END
  presents the finished part (always clamped to your axes);
  `variable_wipe_x` / `variable_wipe_y` — the anchor of the nozzle-wipe pad
  (default −1 = the axis-minimum corner). On another printer or with the pad
  somewhere else, set them once — no macro editing needed.

  ⚠ **Never use a raw `[r2_postproc]` section** (the pre-.82 form, R92…R81):
  Klipper refuses unknown sections outright — „Section 'r2_postproc' is not a
  valid config section", the printer ends up in a halt loop. A settings macro
  (like KAMP's `_KAMP_Settings`) is the only valid carrier; `setup.sh`
  migrates an old section automatically (backup included).

## 24. Cheat sheet: LCD paths & Mainsail commands

**LCD quick paths**

| I want to… | LCD path |
|---|---|
| print with my overwrites | Start Print? > AS LEGACY |
| print exactly as sliced | Start Print? > PRINT AS SLICED |
| system takeover of a sliced file | Start Print? > PRINT AS LEGACY |
| adjust Z live | Live Tuning > Z +0.04/−0.04 |
| hotend/bed/fan/Z-offset fast | Live Tuning > Hot / Bed / Fan / Zoff |
| slow everything down | Live Tuning > Spd per feat > Glob |
| machine limits live | Live Tuning > Velocity |
| flow/PA/retraction live | Live Tuning > Extrusion |
| pause at layer 17 | Live Tuning > Pause & Control > Pause@: 17 |
| skip an object | Live Tuning > Objects (2×) |
| change material preset | Pre-Print > Material > LOAD NOW |
| compare with the file values | Pre-Print > Temperatures > File H:/File B: |
| first layer slower/faster | Pre-Print > 1st layer % |
| calibrate flow | Maintenance > Flow Cal. |
| run a temperature tower | Maintenance > Temp Tower |
| print cable ties | Tools > Cable ties > Create (press 2×) |
| print an angle bracket | Tools > Angles+Flat > Mode > Angle, Settings, Create |
| join two boards flush | Tools > Angles+Flat > Mode > Flat splice, Left/Right, Create |
| print a lithophane | Tools > Lithophane > Images (Create) — slot press, then start |
| print a color picture | Tools > ColorPic > Images — slot press, swap filament at every beep |
| print building bricks | Tools > Bricks > Catalog (count parts) > Create |
| turn a sliced file into a kit | Tools > Bricks > Kit from file > CREATE kit |
| print figures | Tools > Bricks > Figures > Scale/Count > CREATE figure |
| print a gasket | Tools > Gaskets > Settings, Create (press 2×) |
| print a picture frame | Tools > Frames > Settings, Create (press 2×) |
| frame as glue kit | Tools > Frames > Preset 13x18, Border 16+, Create — strips + plate, glue the joints |
| fuzzy skin / dimples on a part | Pre-Print > Texture — pick mode + values, > Apply, check the _TX file in the viewer |
| delete a lithophane image | Tools > Lithophane > Delete image — press the slot twice |
| test ironing | Maintenance > Ironing Cal. |
| purge / cold pull | console `PURGE_MORE` (15 mm) · Maintenance > Filament |
| shutdown the Pi | System > Pi shutdown (2×) |
| cable/lamp hole in a range part | Pre-Print > Range/Stop > Fl.hole / Top hole, then Create |
| which g-code files are outdated | System > File check — console lists every file; Retag old (2×) upgrades them |
| printer off, Pi stays on | PRINTER_POWER_OFF (console — needs the relay, ch. 26) |

**Mainsail — the 20 you will actually use**

```
SHOW_STATUS · SET_MATERIAL MATERIAL=PLA · SET_OVERRIDE_VALUE NAME=… VALUE=… ·
TOGGLE_OVERRIDE NAME=… · CLEAR_OVERRIDES · PRINT_AS_SLICED / PRINT_WITH_OVERRIDES /
PRINT_AS_LEGACY · SET_GLOBAL_SPEED · SET_GLOBAL_ACCEL · SET_LIVE_VELOCITY ·
SET_LIVE_MINIMUM_CRUISE_RATIO · SET_LIVE_PRESSURE_ADVANCE · SET_LIVE_RETRACTION ·
SET_FLOW_RATE · SET_GLOBAL_ACCEL_PERCENT PERCENT=150 · SET_FAN_SCALE · PAUSE · RESUME · CANCEL_PRINT (2×) ·
PAUSE_AT_LAYER LAYER=n · SKIP_OBJECT OBJECT=name · GEN_LABELS TEXT="A|B" ·
GEN_CABLE_TIES COUNT=6 LENGTH=120 · GEN_ANGLES ANGLE=90 WIDTH=25 WALLS=4 INFILL=60 ·
GEN_FRAME PRESET=10x15 DEPTH=8 CLOSURE=BACK HANG=TOP STAND=1 ·
TEXTURE_APPLY FILE=myfile.gcode MODE=BUMPS PATTERN=WAVES SCALE=10 AMP=0.35 ·
SET_LAYER_RANGE FLOOR=3 FLOOR_HOLE=15 TOP_HOLE=28 · SET_NOZZLE_SPLIT STATE=1 ·
FILE_CHECK · FILE_CHECK RETAG=1 CONFIRM=1 ·
CALIBRATE_PA · FLOW_CAL MEASURE=0.46 · TEMP_TOWER_START START=200 END=230 STEP=5 BAND=10
```

**Mainsail's macro panel:** every macro carries a one-line `description:`
(the same text Mainsail shows under the macro name). Type the macro name in
the console with a `?` and no parameters — most macros answer with their
usage line and the valid values instead of doing something.

**Abbreviation decoder** — the short codes the console, M117 and the LCD use:

| Code | Means | Code | Means |
|---|---|---|---|
| **L1 / L2** | layer 1 / layer 2 (temp & fan system, ch. 8) | **PA** | pressure advance |
| **OW / IW** | outer wall / inner wall | **SP / SO** | sparse infill / solid infill |
| **TP / BT** | top surface / bottom surface | **BR / GP** | bridge / gap fill |
| **SU / IR** | support / ironing | **SK / BM** | skirt / brim |
| **FS_* / FA_*** | file's measured speed / acceleration of that feature | **o:ON** | that feature's override is ON |
| **Src:** | where a value comes from: file / overwrite / live | **Now:** | the feature printing right now |
| **LH** | layer height | **CS** | countersink (generator holes) |
| **Vers / V01…** | the generated file's version number | **CLA / LOO** | CLASSIC / LOOP closure (cable ties) |
| **Boss** | thick wall ring around a generated hole | **Bridge-first** | cap layer 1 anchors the top hole edge (no sagging) |
| **Zoff** | Z offset (babystepping total) | **RetLen / RetSpd / Unret** | retract length / speed / unretract speed |
| **MCR** | minimum cruise ratio | **SCV** | square corner velocity |

## 25. Complete macro index
All 150 public macros with parameters (defaults in parentheses; blank = no parameters). Internal helpers (leading `_`) are not user-facing. Grouped by module file — the same file you would edit.

### Sounds — 02_sounds.cfg (4)
| Macro | Parameters | Purpose |
|---|---|---|
| **M300** | P=100, S=1000 | single beep — wrapper; the real beep lives on as M99300 |
| **PLAY_SOUND** | NAME='r2_click' | play a tune by name (ch. 16) |
| **TOGGLE_SOUNDS** | — | sounds on/off (persisted: sound_on) |
| **TEST_SOUNDS** | — | play all 20 tunes in sequence |

### LEDs — 03_leds.cfg (9)
| Macro | Parameters | Purpose |
|---|---|---|
| **SET_LED_STATE** | STATE='idle' | switch the LED pattern (12 states, ch. 17) — applies the nozzle mode + bed light too |
| **NOZZLE_LED** | MODE, BRIGHT, R, G, B | nozzle light: on/off/auto + live dimming + live color (ch. 17) |
| **SET_NOZZLE_SPLIT** | STATE=0/1 | nozzle LEDs on their own EBB42 chain (1) or last LED of the main chain (0) — persisted (ch. 26) |
| **SET_LED_LAYOUT** | STATUS, BED | LED area split — hard-clamped to the chain, persisted in r2_hardware.cfg (ch. 17) |
| **SET_BED_LIGHT** | STATE, TOGGLE, BRIGHT | bed work light on/off + brightness 0–0.5 (ch. 17) |
| **LED_INFO** | — | report chain + pin + areas + switches (console) |
| **TOGGLE_LEDS** | — | frame LEDs off/on (persisted: leds_on) |
| **TEST_LEDS** | — | LED test animation |
| _NOZZLE_SET / _BEDLIGHT_SET | ON, BRIGHT | internal: writes the nozzle / bed-light LEDs (capped 0.5) |

### Notifications — 04_notify.cfg (2)
| Macro | Parameters | Purpose |
|---|---|---|
| **NOTIFY** | TEXT, LEVEL='info', LED, SOUND | notification helper: text + sound + LED in one call |
| **SHOW_STATUS** | — | full status: mode, material, overrides, live values |

### Materials & profiles — 05_materials.cfg (18)
| Macro | Parameters | Purpose |
|---|---|---|
| **SET_MATERIAL** | MATERIAL=<current>, APPLY_PRESET=1 | select material; APPLY_PRESET=1 also loads its preset |
| **SAVE_MATERIAL_TEMPS** | MATERIAL=<current> | save current values as this material's preset — works WITHOUT loading it first (.84) |
| **SHOW_MATERIAL** | — | show the current material + its stored preset |
| **LOAD_DEFAULT_PRESET** | N=1..8 | load standalone default profile N (values + ON switches via _PROFILE_APPLY) |
| **SAVE_DEFAULT_PRESET** | N=1..8 | save the current override state as default profile N |
| **DELETE_DEFAULT_PRESET** | N=1..8 | delete default profile N |
| **DEFAULT_PRESETS_INFO** | — | list all default profiles (slot, material, marker, epoch) |
| **SAVE_FILE_PROFILE** | WHICH=pre | save the selected file's CURRENT pre-print state as its 'pre' profile (.84) |
| **FILE_PROFILE_LOAD** | WHICH=pre/post | load the selected file's profile slot |
| **FILE_PROFILE_DELETE** | WHICH=pre/post | delete the selected file's profile slot (other slot stays) |
| **FILE_PROFILES_INFO** | — | what is stored for the selected file: pre/post, epochs, which one auto-load picks |
| **FILE_PROFILE_AUTO** | FILE=<relpath> (int.) | watcher hook on every file selection: sets the menu flags + applies the newer profile when Auto-load is ON |
| **_PROFILE_APPLY** | SRC=default N= · SRC=file WHICH= FILE= (int.) | the ONE apply path: values + ON switches + feature values + material |
| **_PROFILE_SAVE** | WHICH= FILE= (int.) | snapshot the live state and hand it to the writer |
| **_PROFILE_WRITE** | WHICH= FILE= (int.) | merge the snapshot into file_profiles (other slot + other files preserved), bump the epoch |
| **_FILE_PROFILE_AUTOSAVE** | — (int.) | PRINT_END hook: saves the end-of-print state as 'post' (skips cancelled prints) |

### Temperatures & marks — 06_temp_controls.cfg (12)
| Macro | Parameters | Purpose |
|---|---|---|
| **M104** | S=-1, T | hotend temp — interceptor, redirects by layer (real: M99104) |
| **M109** | S=-1, T | like M104, but waits |
| **M140** | S=-1 | bed temp — interceptor (real: M99140) |
| **M190** | S=-1 | like M140, but waits |
| **M106** | S=255 | part fan — scaling + from-layer-2 rule |
| **M204** | P, S, T | acceleration — interceptor (M99204): feature accel while that feature's override is ON, else global overwrite ON → your accel, else file 1:1 |
| **LAYER_MARK** | — | layer marker (inserted by the post-processor) |
| **M220** | S=100 | speed — interceptor (real: M99220): L1 cap while layer 1 runs; ALWAYS stores the clean global % as g_speed_clean — the base command features use |
| **PAUSE_NEXT_LAYER** | REASON='next layer' | one-shot pause at the next layer boundary |
| **PAUSE_AT_LAYER** | LAYER=0 | one-shot pause at layer n (n greater than 1) |
| **SET_LIVE_HOTEND_TEMP** | T=-1 | change the hotend target live |
| **SET_LIVE_BED_TEMP** | T=-1 | change the bed target live |

### Start dialog & overrides — 07_start_confirm.cfg (8)
| Macro | Parameters | Purpose |
|---|---|---|
| **PRINT_AS_SLICED** | — | start dialog: answer AS SLICED |
| **PRINT_WITH_OVERRIDES** | — | alias for AS LEGACY (merged mode) |
| **PRINT_AS_LEGACY** | — | start dialog: AS LEGACY |
| **CANCEL_PENDING_PRINT** | — | start dialog: cancel (nothing is hot yet) |
| **SET_OVERRIDE_VALUE** | NAME, VALUE | set one override + switch it ON |
| **TOGGLE_OVERRIDE** | NAME='' | flip one override switch |
| **CLEAR_OVERRIDES** | — | all switches OFF (values stay stored) |
| **TOGGLE_START_CONFIRMATION** | — | start dialog on/off (persisted: start_confirm) |

### Print start & end — 08_print_start_stop.cfg (3)
| Macro | Parameters | Purpose |
|---|---|---|
| **PRINT_START** | BED, HOTEND_FIRST, HOTEND_AFTER, BED_AFTER, MATERIAL='PLA', LAYER_HEIGHT=0.2, TOTAL_LAYERS=0, OUTER_WALL_SPEED=0, SUPPORT_SPEED=0, IRONING_SPEED=0 | start choreography — called by the sliced file |
| **START_PRINT** | — | old macro name: marked = no-op · legacy = real legacy start (dialog or auto-prep) |
| **PRINT_END** | — | end choreography: heaters/fans per settings, stats, sound, LED celebration → idle after led_finish_time s, full _PRINT_CLEANUP |
| **SET_LAYER_RANGE** | START, END, FLOOR, FLOOR_SHAPE (0/1), FLOOR_FILL (0/1), TOP, TOP_SHAPE, TOP_FILL, FLOOR_HOLE, TOP_HOLE, BRIM | layer-range excerpt with raft/cap, centered floor+top holes (E14/E27 presets: ch. 5.1); refuses while a print runs (.105) |
| **FIX_FILE** | WHAT=RETRACT/VOL/FLOWCAP/TRAVELACC, CAP=(12), ACCEL=(8000) | repair the SELECTED file in place: retract pairs → G10/G11 · volumetric E → mm · flow cap mm³/s (.85) · travel accel (.85) |

### Pause & filament — 09_pause_filament.cfg (11)
| Macro | Parameters | Purpose |
|---|---|---|
| **PAUSE** | REASON='User' | pause + park (mode-aware) |
| **QUICK_PAUSE** | — | alias for PAUSE |
| **RESUME** | — | the full resume sequence (ch. 6) |
| **CANCEL_PRINT** | — | 1st press arms (expires 60 s, also while paused), 2nd press cancels + _PRINT_CLEANUP |
| **M600** | — | filament change (park, unload, wait for load) |
| **CHANGE_FILAMENT** | — | M600 for humans — works from idle too (heats) |
| **CHANGE_FILAMENT_RESUME** | — | internal continuation after the load |
| **PURGE_MORE** | — | purge 15 mm more (after change/resume) |
| **M0** | — | slicer pause — mapped to PAUSE |
| **M1** | — | slicer pause — mapped to PAUSE |
| _PRINT_CLEANUP | — | internal: resets ALL per-print state (called by PRINT_END/CANCEL/watcher — settings + mesh stay) |

### Live tuning — 10_live_tuning.cfg (35)
| Macro | Parameters | Purpose |
|---|---|---|
| **APPLY_TYPE** | TYPE='' | feature switch: sets current_type + applies the active overrides for THIS feature (speed % x clean global via M99220, absolute accel via M99204, ironing flow via M99221) — injected after every ;TYPE: by the post-processor |
| **SET_OVERRIDE_VALUE** | NAME, VALUE | generic: NAME=feat_spd_<code> / feat_acc_<code> / feat_on_<code> for 16 codes + all legacy names; feat_on=0 resets speed→100% + accel→file M204 + ironing flow→slicer value |
| **SET_GLOBAL_SPEED** | PERCENT=100 | global speed % (M220 style, never capped); the running feature stays on top — re-applied immediately |
| **SET_GLOBAL_ACCEL** | ACCEL=4000 | global acceleration, mm/s²; a feature with its own accel keeps it |
| **SET_GLOBAL_ACCEL_PERCENT** | PERCENT=100 | scales ALL per-feature accel limits by % (10–300) in the same ratio — the global accel itself stays absolute |
| **SET_LIVE_VELOCITY** | VELOCITY=300 | max velocity, live |
| **SET_LIVE_MINIMUM_CRUISE_RATIO** | VALUE=0.5 | minimum cruise ratio, live |
| **SET_LIVE_SQUARE_CORNER** | VALUE=5 | square corner velocity, live |
| **SET_FLOW_RATE** | PERCENT=100 | global flow % (M221) |
| **SET_LIVE_PRESSURE_ADVANCE** | VALUE=0.045 | pressure advance, live |
| **SET_LIVE_PA_SMOOTH** | TIME=0 | PA smooth time, live |
| **SET_LIVE_RETRACTION** | LENGTH, SPEED, UNRETRACT_SPEED, EXTRA | live retraction — one parameter, the others stay |
| **SET_RETRACTION** | RETRACT_LENGTH=0.75, RETRACT_SPEED=35, UNRETRACT_SPEED | firmware retraction — interceptor, override-aware |
| **SET_PRESSURE_ADVANCE** | ADVANCE, SMOOTH_TIME | interceptor — with the PA override ON your value wins |
| **SET_FAN_SCALE** | PERCENT=100 | fan scaling % |
| **SET_FAN_CLAMP** | ON=-1, MIN=-1, MAX=-1, BRIDGE=-1 | fan curve clamp (.85): every M106 runs between MIN/MAX %, BRIDGE lifts the fan on bridge sections (0 = off); -1 = leave unchanged |
| **SET_FEAT_PA** | FEATURE, PA=-1 | pressure advance for ONE feature (.85), 0 = off — applied at its boundaries, global PA returns after |
| **SET_FEAT_SHAPER_OFF** | FEATURE, STATE=-1 | input shaper OFF while one feature prints (.85) — freqs saved/restored, safety net at PRINT_END/cancel |
| **SET_EXTRUDER_DRIVE** | TYPE=DIRECT\|BOWDEN | retraction starting-point profile (.107): direct 0.6mm @ 40mm/s + z-hop off / bowden 4.5mm @ 30mm/s — every value stays freely editable, both directions |
| **SET_UNRETRACT_EXTRA** | EXTRA=-1 | every unretract adds EXTRA mm (.85) — seals the dot after a travel; 0 = off |
| **SET_OUTER_WALL_SPEED/ACCEL · SET_SUPPORT_SPEED/ACCEL · SET_IRONING_SPEED** | PERCENT= / ACCEL= | legacy-friendly per-feature setters: forward to feat_spd/feat_acc + ON — % sits on top of the CLEAN global |
| **SET_IRONING_FLOW** | PERCENT=100 | ironing-only flow override |
| **BABYSTEP_DOWN** | — | Z --0.04 mm live |
| **BABYSTEP_UP_FINE** | — | Z +0.12 mm — quick rescue step |
| **BABYSTEP_DOWN_FINE** | — | Z --0.12 mm — quick rescue step |

### Gantry — 11_gantry_sync.cfg (7)
| Macro | Parameters | Purpose |
|---|---|---|
| **SYNC_GANTRY** | FORCE=0, QUIET=0 | mechanical Z gantry sync — ONE Z stepper/driver only (needs [force_move] + a TMC driver); 2+ Z steppers → use Z_TILT |
| **TOGGLE_GANTRY_SYNC_BOOT** | — | sync at every boot on/off |
| **TOGGLE_GANTRY_SYNC_PRINT** | — | sync at every print start on/off |
| **Z_TILT** | RETRIES, RETRY_TOLERANCE, QUIET=0 | Z_TILT_ADJUST over the [z_tilt] points — 2+ Z steppers only; defaults from the LCD settings, homes first |
| **Z_TILT_INFO** | — | lists the probe points, horizontal move Z, retries + tolerance (console) |
| **TOGGLE_Z_TILT_BOOT** | — | z-tilt at every boot on/off (single-Z printers keep SYNC_GANTRY's switch) |
| **TOGGLE_Z_TILT_PRINT** | — | z-tilt at every print start on/off |

### Maintenance & calibration — 12_maintenance.cfg (35)
| Macro | Parameters | Purpose |
|---|---|---|
| **TUNE_PID** | HEATER='extruder', TARGET=210, FAN=-1, AUTOSAVE=1 | PID tune; FAN=% runs with the fan on (like printing) |
| **CALIBRATE_MESH** | — | full bed mesh now (at bed temperature) |
| **LOAD_BED_MESH** | PROFILE='' | load a mesh profile (menu list) |
| **DELETE_MESH** | PROFILE='' | delete a profile (2x confirm) |
| **LEVEL_BED_SCREWS** | — | screw leveling with console report |
| **CALIBRATE_PROBE_OFFSET** | — | probe Z offset — paper method, TESTZ, SAVE_CONFIG |
| **CALIBRATE_EXTRUDER** | TEMP=210, MEASURED=0, STEP='' | extruder steps: mark 120 mm, extrude 100, enter the rest |
| **TEST_RETRACTION** | — | retract/unretract pairs at temperature |
| **LOAD_FILAMENT** | — | heat if cold + feed load_length mm (default 60, LCD 20-150; .39) |
| **UNLOAD_FILAMENT** | — | heat + reverse (unload_length, LCD 40-150) |
| **CALIBRATE_PA** | TEMP, BED, START, STEP, LINES, LEN, SLOW, FAST, ACCEL, LAYER, SPACING, WIDTH — all from menu/preset | PA pattern print |
| **PA_RESULT** | SEG=0, VALUE=-1 | SEG=best line: PA computed + set live · VALUE=... skips the math |
| **CALIBRATE_PA_SMOOTH** | START, STEP, LINES (.004/.001 def.) | smooth-time pattern with YOUR PA fixed; mesh + prime first, babystepping works during the test |
| **PA_SMOOTH_RESULT** | SEG=n | line n → smooth = start+(n-1)·step, set live + override ON |
| **COLD_PULL** | STEP='run', HOT=240, PULL=100 | cold pull wizard (2 steps + alarm) |
| **CALIBRATE_SHAPER** | AXIS='BOTH', FREQ_START, FREQ_END, MAX_SMOOTHING, AUTOSAVE | input shaper measurement (ADXL; ISHAPER.md) |
| **DUMP_RESONANCES** | AXIS='BOTH' | export raw shaper data |
| **RESONANCE_DIAGRAM** | AXIS='BOTH', MODE='PRINT'/'PLOT' | CSV → printed/plotted diagram with the shaper table |
| **SHAPER_RESULT** | AXIS, TYPE, FREQ | shaper calculator: table show / apply the picked shaper + boot override |
| **BRIDGE_TEST** | — | build the bridging test file (long + short bridge) |
| **PLOT_TEXT** | FILE='notes.txt' | draw a text file from the gcodes folder on paper |
| **PLOT_STATUS** | — | draw the SHOW_STATUS report on one page |
| **SET_PLOT_SPEED** | PCT=100 | live while plotting: pen speed % (M220) |
| **SET_PLOT_PENZ** | DZ=0.05 | live: pen pressure fine tune (Z babystep) |
| **SET_PLOT_SHIFT** | X=, Y= | live: shift the whole drawing X/Y |
| **PLOT_TUNE_RESET** | — | reset the plot start overrides to neutral |
| **_PLOT_NAME_SET_CHAR** | POS, CH | plot text file editor (internal) |
| **PLOT_NAME_DEL_CHAR** | — | plot text file editor: delete char |
| **SAVE_MESH_AT_TEMP** | — | save the mesh as a bed-temp profile (e.g. r2_60C) |
| **MESH_BY_INDEX** | INDEX=-1 | load a mesh by menu index |
| **UNLOAD_MESH** | — | clear the mesh + level again next time |
| **SELF_TEST** | — | system self test — run before long prints |
| **FLOW_CAL** | MEASURE=<menu>, TARGET | wall measurement -> suggested flow % |
| **FLOW_CAL_APPLY** | — | apply the suggested flow (override ON, 50-150 % guard) |
| **TEMP_TOWER_START** | START=200, END=230, STEP=5, BAND=10 | temperature tower (marker + legacy files) |
| **TEMP_TOWER_STOP** | — | stop early (otherwise the last temperature holds) |
| **IRONING_CAL** | F1=10, F2=15, F3=20, S1=20, S2=30, S3=40, TEMP=200, BED=60, LAYER=0.2, LEN=40, WID=24, ACCEL=3000 | 3-zone ironing test card |

### System — 13_system.cfg (7)
| Macro | Parameters | Purpose |
|---|---|---|
| **SYS_FIRMWARE_RESTART** | CONFIRM=0 | Klipper restart (2x) |
| **SYS_HOST_RESTART** | CONFIRM=0 | host services restart (2x) |
| **SYS_SHUTDOWN** | CONFIRM=0 | heaters/fans/LEDs off, then Pi shutdown (2x) |
| **SYS_SAVE_CONFIG** | CONFIRM=0 | guarded SAVE_CONFIG: print guard + pending guard + dark-LCD warning (2x) |
| **FORCE_END_PRINT** | CONFIRM=0 | emergency: ALWAYS ends the print cleanly, even from a wedged state |
| **HOST_RESTART_INFO** | — | explains what a host restart does |
| **EMERGENCY_STOP** | — | immediate full halt |
| **FILE_CHECK** | RETAG=0, CONFIRM=0 | g-code inventory: tag version census (current/old/untouched/plotter) on console + LCD; `RETAG=1 CONFIRM=1` upgrades old files (.r2bak backup, never while printing) |

### Labels — 16_labels.cfg (9)
| Macro | Parameters | Purpose |
|---|---|---|
| **GEN_LABELS** | TEXT, W, H, FONT, BASE_LAYERS, TEXT_LAYERS, LAYER_H, FIRST_H, IRONING, HOLE, HOLE_D, BRIM, GAP, COLOR2 | console/Mainsail label job: `GEN_LABELS TEXT="A\|B" W=60 H=30 HOLE=LEFT` — sets everything + creates the file |
| **LABEL_GENERATE** | — | create the file for the queued labels (bumps label_gen_nonce; the watcher builds it) |
| **LABEL_ADD** | — | append the edited text to the queue (max 24) |
| **LABEL_DEL_LAST** | — | remove the last label from the queue |
| **LABEL_CLEAR_ALL** | CONFIRM=0 | clear the whole queue (2x) |
| **LABEL_SHOW_TEXT** | — | show the edit buffer (LCD + console) |
| **LABEL_DEL_CHAR** | — | delete the character at the cursor position |
| **LABEL_CLEAR_TEXT** | — | clear the edit buffer |
| **LABEL_INFO** | — | queue + size + font + bed-fit info |

### Part generators — 17_generator.cfg (13)
| Macro | Parameters | Purpose |
|---|---|---|
| **GEN_CABLE_TIES** | COUNT=6, LENGTH=120, WIDTH=8, LAYERS=3, VARIANT='CLASSIC', LAYER_H=0.2, BRIM=1 | console/Mainsail cable-tie job: `GEN_CABLE_TIES COUNT=6 LENGTH=120 VARIANT=LOOP` — sets everything + creates the file (VARIANT: CLASSIC one-way pawl · LOOP adjustable bead loop, reusable) |
| **LITHO_CREATE** | INDEX=0 | lithophane from image slot INDEX (0 = newest picture in Tools > Lithophane; big jobs run in a background thread) |
| **LITHO_DEL_SLOT** | INDEX=0 | delete image slot INDEX — 2-press logic like the LCD: first call arms, the second deletes (plotter `.gcode` stays) |
| **GEN_SEAL** | OD=40, ID=20, HEIGHT=1.2, PROFILE='FLAT', IRONING=0, LAYER_H=0.2 | console/Mainsail gasket job: `GEN_SEAL OD=30 ID=15 HEIGHT=2 PROFILE=NUT` — groove + two sealing lips |
| **CABLE_TIE_GENERATE** | — | create the tie file from the stored settings (bumps cable_tie_nonce; the watcher builds it, beeps + selects) |
| **CABLE_TIE_INFO** | — | every tie setting in one listing + material tip |
| **LITHO_INFO** | — | lithophane settings + how many images are ready |
| **SEAL_INFO** | — | gasket settings + NUT/material tips |
| **SEAL_GENERATE** | — | create the seal file from the stored settings (bumps seal_nonce) |
| **GEN_FRAME** | PRESET='', W=102, H=152, DEPTH=8, BORDER=12, CORNER=6, SHAPE='RECT', CLOSURE='BACK', HANG='TOP', STAND=0, IRONING=1, INFILL=60 | console/Mainsail frame job: `GEN_FRAME PRESET=A6 DEPTH=16 CLOSURE=BACK HANG=OFF STAND=1` — bed fit checked, kit fallback, guard errors beep + show |
| **FRAME_GENERATE** | — | create the frame file from the stored settings (bumps frame_nonce) |
| **FRAME_INFO** | — | every frame setting in one listing + closure explanation |
| **GEN_ANGLES** | COUNT=2, ANGLE=90, LEG_A=60, LEG_B=60, WIDTH=25, LAYERS=6, HOLES=2, HOLE_D=4, CS=1, STIFFENER=1, WALLS=2, INFILL=100, IRONING=0, FLAT=0, LAYER_H=0.2 | console/Mainsail angle/flat job: `GEN_ANGLES ANGLE=45 LEG_A=80 LEG_B=50 STIFFENER=2` — CS=1 countersunk · FLAT=1 flat connector |
| **ANGLE_GENERATE** | — | create the plate file from the stored settings (bumps angle_nonce) |
| **ANGLE_INFO** | — | every angle/flat setting + the auto-hole rules |
| **TEXTURE_APPLY** | FILE='', MODE='OFF', THICK, DENSITY, PATTERN, SCALE, AMP, DIR='OUT', OUT= | fuzzy skin / shaped bumps for the SELECTED (or FILE) g-code: `TEXTURE_APPLY MODE=FUZZY THICK=0.3 DENSITY=100` — new `Vnn_<name>_TX` file in the background — selected under QUEUE, but never auto-STARTED (ch. 5.9) |
| **_GEN_OUT_SET** | OUT=QUEUE/PREVIEW (SELECT/ONLY/1/0) (int.) | the sticky generator output switch (.84, ch. 5.0) — every `*_GENERATE` macro also takes a per-run `OUT=` |

### Building bricks & figures — 19_bricks.cfg
| Macro | Parameters | Purpose |
|---|---|---|
| **GEN_BRICKS** | CODES='B2x4:3\|P2x2:2' | console/Mainsail brick job: sets the queue (code:count, `\|` separated, max 120) and creates `V01_Bricks.gcode` |
| **BRICK_ADD** | CODE='B2x4', COUNT=2 | add COUNT × CODE to the queue (same codes merge; unknown code or count outside 1–99 rejected) |
| **BRICK_DEL_LAST** | — | drop the last queue entry |
| **BRICK_CLEAR** | CONFIRM=1 | empty the queue (2-press: first call arms) |
| **BRICK_SHOW** | — | list the queue |
| **BRICK_INFO** | — | settings + geometry summary |
| **BRICK_CREATE** | OUT=QUEUE/PREVIEW | build the file from the queue (bumps bricks_nonce; the watcher builds, beeps + selects) |
| **GEN_BRICKKIT** | SRC='box.gcode', INDEX=0–4, DETAIL=AUTO/MICRO/SMALL/BIG, MODE=BY_LAYER/BY_OBJECT, COLORS=1–8 | sliced file → stylized kit (source = the file selected in the file list, like Texture; Mainsail: SRC=name or INDEX=0–4 = recent jobs; no silent newest-job fallback) |
| **GEN_FIGURES** | SCALE=25–300, COUNT=1–24 | figures at % scale — 5 parts each, assembly without glue; only 100 % mates with the system |

### Color picture — 18_colorpic.cfg
| Macro | Parameters | Purpose |
|---|---|---|
| **GEN_COLORPIC** | SRC='photo.png', WIDTH=25–230, BANDS=2–8, BANDH=0.4–3, COLORS='WHT,GRY,BLK', LAYER_H, IRONING=0/1, BRIM=0–8, SWAP=0/1, CONTRAST=0/1 | console/Mainsail color picture: sets everything + creates (SWAP=0 prints every band without a filament change) |
| **COLORPIC_CREATE** | INDEX=0–9, SRC='photo.png', OUT= | create from image slot INDEX / explicit SRC / the last picked lithophane image (bumps colorpic_nonce; the watcher builds, beeps + selects) |

### KAMP — 14_kamp.cfg (5)
| Macro | Parameters | Purpose |
|---|---|---|
| **TOGGLE_KAMP_MESH** | — | KAMP adaptive mesh on/off |
| **TOGGLE_KAMP_PURGE** | — | KAMP purge on/off |
| **SET_KAMP_PURGE_TYPE** | TYPE='LINE' | KAMP purge style: LINE or VORON |
| **TOGGLE_KAMP_SMART_PARK** | — | KAMP smart parking on/off |
| **KAMP_STATUS** | — | KAMP configuration report |

### Objects — 15_objects.cfg (4)
| Macro | Parameters | Purpose |
|---|---|---|
| **SKIP_OBJECT** | NAME='' | arm a skip for one object (2x confirm) |
| **SKIP_CURRENT_OBJECT** | — | skip the object currently printing (2x) |
| **SKIP_DISARM** | — | disarm a pending skip |
| **SHOW_OBJECTS** | — | list objects + skip state |

---

*Built and tested for one purpose: printing happily — with R2-D2 keeping watch.*

---

## 26. Electronics & expansion — U2C + EBB42 + Relay V1.2

One four-wire harness to the toolhead instead of a thick bundle, the printer
switchable off while the Pi stays on, nozzle LEDs at the print head. All of
this is OPTIONAL — the system runs unchanged on a bare SKR Mini E3 V3. Pin
data from BigTreeTech's GitHub (EBB repo + Relay V1.2 manual) and Klipper's
`sample-bigtreetech-ebb-canbus-v1.2.cfg`.

### 26.1 The architecture — and why

```text
230V mains --L--[RELAY V1.2]--L--> PSU 24V          (relay switches the PHASE)
230V mains --N----------------> PSU 24V             (direct, never switched)
PE ----------------------------------> PSU + frame  (ALWAYS direct!)
PSU 24V out ---> SKR Mini E3 V3  (board, bed, motors, LCD, frame LEDs)
PSU 24V out ---> EBB42 VIN       (hotend, toolhead fans) - via the SAME relay
Pi Zero 2  <== OWN 5V USB PSU ==  (never powered from the SKR again!)
Pi Zero 2 USB ---> U2C V2.1 ---> CAN (H/L, twisted) ---> EBB42 at the toolhead
SKR free pin  ---> Relay 5V_IN   (HIGH while Klipper runs = printer ON)
```

- **Pi on its own 5V USB PSU** (≥ 2.5 A headroom): the relay kills the
  printer, the Pi stays — exactly what you wanted. Never power the Pi from
  two sources at once: REMOVE the old 5V-from-SKR line.
- **U2C V2.1** hangs on the Pi's USB port (powered by the Pi — stays alive).
  It converts USB to CAN. 120 Ω jumper ON (it is one end of the bus).
- **EBB42 CAN V1.2.1** sits at the toolhead (mounted at the extruder stepper)
  — one 4-wire harness replaces heater + 2 fans + probe + stepper + LED
  cables. 120 Ω jumper ON (the other end). EXACTLY TWO terminators total.
- **Relay V1.2 in the 230V phase**: rated 10 A / 250 VAC — the whole printer
  draws ~1.5 A at 230 V. The module's control input (5V_IN, logic 3.3–5 V)
  comes from a free SKR pin that Klipper holds HIGH. Klipper dead = pin LOW
  = printer OFF: a hard FAIL-SAFE (a crashed host can never leave heaters
  powered). Your DC-DC 5V module is not needed in this architecture — keep
  it as a spare.
- **UART stays**: the SKR keeps talking to the Pi on the UART pins (the Pi
  Zero's only USB data port is used by the U2C). Add a 10 kΩ resistor in
  series with each UART line so the always-on Pi cannot phantom-power the
  unpowered SKR through its RX pin when the relay is off.

### 26.2 The cable list — EBB at the extruder stepper

Measure along the real route (carriage → X extrusion → chain → electronics
bay); these are proven starting points for an Ender-3 class frame:

| # | Cable | From → To | Type / gauge | Length | Connector at the EBB |
|---|---|---|---|---|---|
| 1 | 24 V + GND | PSU out (relay-switched) → EBB | 2 × silicone 0.5 mm² (20 AWG) | ~1.4 m | VIN screw terminal (mind polarity + onboard fuse) |
| 2 | CAN-H / CAN-L | U2C CAN port → EBB | twisted pair 0.14–0.25 mm² (26–24 AWG) | ~1.4 m | 4-pin CAN (use H, L, GND; verify pin order on BOTH silkscreens — never trust wire colors) |
| 3 | Extruder stepper | motor → EBB | existing 4-pin, shortened | 10–15 cm | motor header (onboard TMC2209) |
| 4 | Hotend heater | cartridge → EBB | existing silicone, shortened | 15–20 cm | HE terminal (40 W ≈ 1.7 A, EBB allows 5 A) |
| 5 | Hotend thermistor | → EBB | existing, shortened | 15–20 cm | TH0 (PA3) |
| 6 | Hotend fan | → EBB | existing, shortened | ~15 cm | FAN (PA1) — max 1 A |
| 7 | Part fan | → EBB | existing, shortened | ~20 cm | FAN (PA0) — max 1 A |
| 8 | MicroProbe | → EBB | existing BLTouch-style, shortened | 20–25 cm | probe port: signal PB8, control/power PB9 (MicroProbe: 3rd wire = POWER) |
| 9 | Nozzle LEDs | strip → EBB | 3-pin (5 V / GND / DATA) | 15–20 cm | RGB port (PD3) — max ~15 LEDs full white (5 V/1 A) |
| 10 | Filament sensor (optional) | → EBB | 2-pin | ~20 cm | PB4 (switch) or PB3 (motion) |

Stays where it is: **X endstop** (stationary at the gantry — stays on the
SKR), **frame LEDs 1–4** (SKR neopixel port, chain_count 4 after the split),
bed + Z + Y (SKR). Reuse your existing cables by SHORTENING them at the
toolhead end — the long run to the bay is now only the 4-wire harness.

### 26.3 Firmware: flashing the EBB42 (once)

1. On the Pi: `cd ~/klipper && make menuconfig` — STM32, **STM32G0B1**,
   8 MHz crystal, **CAN bus (on PB0/PB1)**, CAN speed **1000000** (matches
   BTT's precompiled firmware; if you build for 500 k, change can0 too),
   8 KiB bootloader (katapult).
2. `make` → flash via DFU: USB-C jumper for USB power, hold RESET+BOOT,
   release RESET then BOOT, `lsusb` shows the DFU device, flash with
   `make flash FLASH_DEVICE=...`.
3. Bring CAN up on the Pi (`/etc/network/interfaces.d/can0`, bitrate matching
   the firmware, `sudo reboot`), then
   `~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0`
   → `Found canbus_uuid=...`.
4. Copy the `[mcu EBB]` block from `printer.cfg.example` into printer.cfg.

### 26.4 printer.cfg changes (full template in printer.cfg.example)

Move to the EBB: extruder stepper (PD0/!PD1/!PD2, TMC2209 UART PA15), hotend
heater (PB13) + thermistor (PA3), part fan (PA0), hotend fan (PA1),
MicroProbe (PB8/PB9), optional filament sensor (PB4), nozzle LEDs (PD3).
Delete the old copies on the SKR pins. Then: `[neopixel printer_leds]`
chain_count 5→4 (frame only) + `[neopixel nozzle_led]` on EBB:PD3 +
uncomment `[led_effect r2_nozzle_on_split]` in 03_leds.cfg + `SET_NOZZLE_SPLIT
STATE=1` (once — persisted). Frame and nozzle effects then work exactly as
before, just on two chains.

### 26.5 Relay V1.2 — printer OFF, Pi stays on

Wiring: mains L into the relay's AC-in, AC-out to the PSU's L (N and PE
direct). 5V_IN + GND of the relay to the SKR's `[output_pin power_hold]` pin
(`value: 1`, `shutdown_value: 0`). The relay's button connector takes any
momentary switch for manual power-on. `PRINTER_POWER_OFF` (template in
printer.cfg.example): refuses while printing, heaters off, then drops the
pin. Power-on flow: press the button → boards boot → **FIRMWARE_RESTART**
(the MCUs were completely off). Add the macro to your System menu or console
— the system's `SYS_SHUTDOWN` (Pi off) stays as it is.

**SAFETY — read before touching mains**

- 230 V is lethal. Work only with the plug pulled; if you are not sure, have
  an electrician do the mains side. The relay PCB carries live power on open
  pads — mount it in the enclosed electronics bay, away from anything
  conductive, "No touch! High voltage danger!" is printed on it for a reason.
- NEVER switch or interrupt PE. Only the L conductor goes through the relay.
- Wire gauge: mains side 0.75 mm²+ with ferrules and strain relief; 24 V
  bed path stays untouched (it runs through the SKR, not the relay).
- The 10 A relay contact is for the whole printer at ~1.5 A — do NOT use it
  to switch 24 V DC directly (arcing!) — on the DC side the bed alone draws
  ~10 A: over the rating and DC arcs do not self-extinguish.
- Insulate everything, check every crimp twice, measure before powering up
  (with everything off: CAN-H↔CAN-L should read ~60 Ω = two 120 Ω in
  parallel — the standard termination check).
- After a relay-off, the EBB was unpowered while Klipper ran — expect one
  "MCU shutdown/lost" message; FIRMWARE_RESTART after power-on is normal.

### 26.6 NeoPixel limits at the EBB

The EBB42's RGB port shares the board's 5 V rail — budget 1 A total:
**~15 WS2812 at full white is the hard ceiling**. The system caps every
channel at 0.5 anyway (board protection), so 15 LEDs run at ~50 % brightness
without ever stressing the rail. More LEDs? Feed the strip's 5 V from its
own supply (common GND!), keep only DATA from the EBB — and keep the cap.

---

## Appendix A: Installation (detailed)

### A.1 Requirements

- Klipper + Moonraker + Mainsail (or Fluidd), path `~/printer_data/`
- the 15 macro modules + `menus/lcd_menues.cfg`
- `[save_variables]` — the memory (survives restarts)

### A.2 printer.cfg checklist (see printer.cfg.example)

| Section | Why / Notes |
|---|---|
| [save_variables] | ALL settings/presets live here — exact path matters |
| [virtual_sdcard] [pause_resume] [display_status] [respond] [exclude_object] | infrastructure; exclude_object unlocks adaptive mesh + object skip + smart parking |
| [idle_timeout] timeout: 3600 | pause management saves/restores this |
| [firmware_retraction] | live retraction + retraction overrides + test |
| [filament_switch_sensor filament_sensor] | runout handling — NAME matters, pause_on_runout: False |
| [pwm_cycle_time beeper] pin PB5 | sounds — pwm_cycle_time NOT output_pin (runtime frequency!) |
| [neopixel printer_leds] PA8, 5 LEDs | LED engine (1-4 frame, 5 nozzle) — no extension needed |
| [display] (st7920) | LCD menus (12864, 16 characters per line) |
| [force_move] enable_force_move: True | SYNC_GANTRY needs SET_KINEMATIC_POSITION |
| [screws_tilt_adjust] / [bed_mesh] + adaptive_margin: 5 | leveling / meshing |
| [probe] / [resonance_tester]+[adxl345] | see A.3 / optional shaper calibration |

```
[include klipper-e3-r2d2/macros/01_state.cfg]
... 02 .. 15 ...
[include klipper-e3-r2d2/menus/lcd_menues.cfg]
-- at the END of printer.cfg; macros first, menus last
```

**A.2.1 The real bed — [gcode_macro _R2_CONFIG] (R92, R104.2 — required once):**
this machine's `position_max` is lifted on purpose (micro probe + bed mesh
rides beyond the plate). So the generators, the prime line and the park
corners read the REAL printable bed from this section — add it once:

```
[gcode_macro _R2_CONFIG]
variable_bed_min_x: 0.0
variable_bed_max_x: 220.0
variable_bed_min_y: -3.0
variable_bed_max_y: 217.0
gcode:
    # config carrier only - never runs
```

Without it everything falls back to the Ender-3 default 220×220 and the
console notes that on every watcher start. Optional positions (R104):
`variable_present_x`/`variable_present_y` (PRINT_END part presentation,
default 10/228) and `variable_wipe_x`/`variable_wipe_y` (nozzle-wipe pad
anchor, −1 = axis-minimum corner) — all clamped to the axes, see chapter 23.
A raw `[r2_postproc]` section (pre-.82) HALTS Klipper — `setup.sh` migrates it.

### A.3 Z-probe variants

- Stock probe with offsets (MicroProbe !PC14, x/y offset): works 1:1
- BLTouch/3DTouch: [probe] with pin + offsets; `samples_tolerance: 0.15` against dirty points
- Inductive/capacitive: same section; mind the sensing distance on PEI spring steel
- Klicky/Euclid: works — docking macros are yours; mesh runs via BED_MESH_CALIBRATE
- No probe: mesh + LEVEL_BED_SCREWS unavailable; level via [bed_screws], Z-offset by hand

### A.4 Filament sensor variants

```ini
[filament_switch_sensor filament_sensor]
switch_pin: !PC15     # YOUR pin
pause_on_runout: False
runout_gcode: _FILAMENT_RUNOUT
insert_gcode: _FILAMENT_INSERTED
```

Motion sensors (BTT Smart) may add `runout_distance: 3.0`. Without a sensor
everything else runs fine — runout simply never triggers.

### A.5 LEDs

5 LEDs on PA8 (GRBGR): 1-4 = frame effects, 5 = nozzle light. Effects come from
the klipper-led_effect extension (julianschill) — 12 frame states, r2_idle
autostarts. The nozzle light has its OWN switch (ch. 17): AUTO (work light while
printing) / ON (always on, your color — a tool light that even stays available
with the frame LEDs OFF) / OFF, plus live dimming and color (LCD 'Quick Macros >
Nozzle LED' or NOZZLE_LED). More pixels: edit [neopixel printer_leds] + the
effects in 03_leds.cfg — POWER RULE: every channel stays ≤0.5 (ch. B: power).

## Appendix B: Power & electrics

Voltage domains, safe supply for the Pi Zero 2 W and Neopixels, the UART serial
link, multi-PSU ground rules and silent-fan mods. Based on the BTT wiring guide
and BTT/community findings. **Verify every rail with a multimeter before
connecting anything.**

### B.1 Voltage map

```
230 V mains -> [24 V PSU] -> bed heater (HB, 20 A fuse) | hotend | steppers | fans | probe VIN
                             -> [SKR mini E3 v3.0]  (onboard 5 V buck ~1 A max - logic only!)
                             -> [DCDC 24V->5V >=3 A] -> Pi Zero 2 W + Neopixels (own rails)
```

### B.2 What the onboard 5 V buck can (not) do

- Onboard buck of the SKR mini E3 v3.0: **~1 A max** (community consensus). BTT's
  own wiring guide: the board is NOT capable of powering a Raspberry Pi.
- Pi Zero 2 W + 5 Neopixels from the board 5 V = right at that limit → brown-outs,
  unstable Pi, SD corruption risk.
- **Official upgrade path:** the green **Neo-PWR1 jumper** selects the 5 V source —
  onboard buck OR the plug-in **BTT DCDC Mode V1.0 module** (MP1584, ~3 A ideal,
  BTT documents up to 30 Neopixel). Alternative: any external 24V→5V buck ≥3 A.

### B.3 Target wiring — one ground star, never parallel plus-rails

```
24V PSU --+24V--> SKR (VIN+/VIN-)          SKR --UART 3 wires--> Pi
          --+24V--> [DCDC 24V->5V] --+5V--> Pi (USB-PWR or GPIO 2/4 + GND 6)
                                  +--5V--> 5x Neopixel (data: PA8 + series R)
GND: every V- lands on ONE star point. Only GND is shared -
     NEVER tie +5 V of two sources together. SW_USB jumper: REMOVE.
```

**Golden rules:** 1) tie ALL V− together at one star point. 2) NEVER parallel +5 V
of two sources. 3) Remove the SW_USB jumper (USB-5 V backfeed). 4) Fuse each 5 V
rail; Pi wiring ≥24 AWG. 5) Measure before first connect: 5.0-5.2 V. 6) Pi GPIO
5 V bypasses the polyfuse — only from a verified, steady source.

### B.4 Powering the Pi Zero 2 W — three options

| Option | How | Verdict |
|---|---|---|
| from the SKR 5 V | 5 V + GND from the board | ✗ ~1 A is already spent — not recommended |
| **USB PWR-IN (micro-USB)** | 5 V ≥2.5 A from the buck/PSU | ✓ cleanest: own cable, keeps polyfuse path |
| GPIO pins 2 (5V) + 6 (GND) | direct into the header | ✓ ok from a measured rail — bypasses the Pi polyfuse |

### B.5 UART instead of USB (TX/RX)

```
Pi Zero 2 W header          SKR mini E3 v3.0 (TFT port)
pin 8  TXD  ----------------> TFT pin 2 RX        (crossover!)
pin 10 RXD  <---------------- TFT pin 3 TX
pin 6  GND  <---------------- TFT pin 4 GND       (mandatory)
```

Pi: `/boot/config.txt` → `enable_uart=1`, `dtoverlay=disable-bt`;
`/boot/cmdline.txt` → remove `console=serial0,115200`. Klipper firmware
(make menuconfig): STM32 → STM32G0B1 → Serial (on USART2 PA3/PA2), bootloader
28 KiB. Then `[mcu] serial: /dev/ttyAMA0 · baud: 250000 · restart_method: command`.
Pin numbers: verify against the BTT pinout PDF of your board revision.

### B.6 Neopixels safely on external 5 V

- **1000 µF electrolytic** across +5 V/GND at the first pixel (inrush)
- **330-470 Ω series resistor** right before DIN (protects pixel 1)
- **common ground with the SKR is mandatory** — otherwise the 3.3 V data has no reference
- long wires or ghost pixels → 74AHCT125 level shifter
- Budget: 5 px × 60 mA = 0.3 A worst case (full white) — a ≥3 A buck has headroom

### B.7 Silent fan mods

| Mod | Wiring | Notes |
|---|---|---|
| 24 V silent fans | plug & play into FAN0/1/2 | simplest — FAN ports run at the 24 V rail |
| 12 V fans (Noctua…) via buck | buck 24V→12V; fan+ from buck, fan− into the board FAN port (low-side) | common ground comes free (same PSU); verify polarity |
| electronics-bay fan | small fan on the electronics housing | keeps drivers + buck cool |

Hotend heatsink fan: keep at 100% whenever the hotend is hot (enforced by the
system). Better a quiet fan at full speed than a fast one slowed down.

### B.8 First-power-on checklist

1. Buck output measured: 5.0-5.2 V BEFORE the Pi or any pixel is connected.
2. Continuity: every V− lands on the star point.
3. NO continuity between separate +5 V rails.
4. SW_USB jumper removed; Neo-PWR1 set to your 5 V source.
5. All joints soldered + heat-shrunk; no stray strands.
6. Boot order: 24 V PSU → SKR → buck rails stable → Pi → LEDs.

### B.9 Where do I connect what? (quick reference)

| Signal / Load | Comes from | Goes to | Watch out |
|---|---|---|---|
| Pi Zero 2 W, 5 V | DCDC/buck 5 V (≥2.5 A) | micro-USB PWR (best) or GPIO 2+6 | GPIO path bypasses the Pi polyfuse |
| Neopixels, 5 V | same buck (LED rail) | pixel 1 +5 V | 1000 µF + common ground with the SKR |
| Neopixel data | SKR pin PA8 (3.3 V) | 330-470 Ω → DIN of pixel 1 | 74AHCT125 for long wires |
| UART serial | Pi GPIO 14/15 | TFT port RX/TX (crossover) | GND mandatory · verify BTT pinout |
| Filament sensor | 5 V + GND (SKR) | signal → !PC15 | pause_on_runout: False |
| Silent fans 12 V | buck 24V→12V | fan+ from buck, fan− to FAN port | low-side switching — polarity! |

## Appendix C: First start & updates

- upload the folder → includes at the end of printer.cfg → RESTART
- console: `Macro system OK: all 17 modules loaded and current (build R2-2026-09-07)`
- ~10 s later: boot sound + LED animation
- SHOW_STATUS → mode, material, overrides · Maintenance > Tests > demos + self test

**Updating (simple):** 1) upload the ZIP in Mainsail into the **config
folder** (where printer.cfg lives — next to the `klipper-e3-r2d2` folder, not
inside it), 2) SSH: `bash ~/printer_data/config/klipper-e3-r2d2/update.sh` —
it finds the newest uploaded ZIP, unzips it over the old folder, checks the
includes and the `#` blocker and restarts Klipper and r2-postproc (python3
fallback if `unzip` is missing; older ZIPs are skipped unless `--force`; the
uploaded ZIP may stay in the folder). Coming from ≤.47 (no update.sh on the Pi
yet): `cd ~/printer_data/config && unzip -o <zip> && bash klipper-e3-r2d2/update.sh`.
No new include lines — if you come from ≤.46 add the one
`[include klipper-e3-r2d2/macros/16_labels.cfg]` line. Mixed old/new files
are detected by _CHECK_INSTALL at boot. All settings live in variables.cfg
and survive every update.

**Daily health check:** SELF_TEST + SHOW_STATUS before long prints.

---

## Appendix D: Version history

Only the milestones — the full reasoning lives in SESSION_STATE.md.

| Version | Core changes |
|---|---|
| .93 | **Bausteine Runde 2 + Hardcore-Stresstest (R132)** — Katalog 45 → **76 Codes**: **9 LCD-Kataloggruppen** (Bricks/Plates/Tiles + NEU Slopes · S, Inverted Slopes · I, Arches/Bögen · A, Technic/Axle · H+C+J+RT, Round · R+RP) · **Figuren**: MODE=SINGLE (**am Stück** — wirklich ohne Klemmelemente, nicht zerlegbar) oder klassisch PARTS (5 Teile), Arme LIEGEND gedruckt (echte Durchgangs-Röhrchen), COLORS 1–4 (Zonenfarben: Beine/Torso/Arme/Kopf), BRIM 0–8, COLORMODE BY_LAYER/BY_OBJECT · **Bricks**: COLORS 1–8, MODE BY_LAYER/BY_OBJECT, BRIM 0–8 · **Zentrierte Anordnung = Generelle Regel für ALLE Generatoren** (auch Bausatz-Platten) · **Fix-then-Reload**: RetractFix/FlowCap/Travel/Vol laden die Datei nach dem Fix automatisch neu — nur noch Start bestätigen (R132-Feldlog: Fixes unterbrachen die Warteschlange; Start-Dialog wird jetzt auf eigenem sauberen Pfad freigegeben) · **Hardcore-Stresstest** tools/r140_stress.py (~41.000 Checks: 76-Code-Generationsmatrix, Modi/Brim/Farben, Jinja-Balance + Render ALLER Makro-Bodies, Klipper-Command-Lint, statische Regressionen der Bug-Klassen) — **7 echte Bugs gefunden und gefixt**: unbalanciertes Jinja-if in GEN_BRICKS (Config wäre auf dem Drucker nicht ladefähig), TUNE_PID-Aufruf über zwei Zeilen (Parameter nie wirksam), offenes Anführungszeichen in CABLE_TIE_INFO, fehlendes M83/G90 in Bricks/Figuren/Bausatz, triviales ;TYPE:Custom am Dateiende, Bausatz ohne LAYER_MARK + APPLY_TYPE TYPE=Custom (pretty name = Malformed command), Figuren-SINGLE ohne BRIDGE im TYPES-Header · Analysen: **Portabilität ohne Beep/LCD**, **Web-UI auf dem Moonraker-Host** (Machbarkeit: ja — statisches SPA + vorhandener nginx), **LCD-Menüs auf anderen Displays** (docs/). Batterie: render 1601/1601 · Megatest 157 Läufe/163 Dateien · Stresstest 41.111 Checks · Systemtest 221/0 · Validator sauber. ||
| .92 | **Dokumentation komplett überholt (R131)** — das Handbuch (MD + PDF) auf den Stand von .91/.92 gebracht: **veraltete Passagen entfernt/ersetzt** — Lithophane FLAT (alte „Terrassen-Relief“-Beschreibung → Stufen-Druck mit StepL/Farbwechsel AUS-LETZTE-JEDE/Rahmen/Kontrast/Purge-Turm), Rahmen-Verschluss (altes „Bajonett, 2,5mm schieben“ → Snap-In-Rückseite mit 4 Wand-Nubs + 0,8mm/Side Foto-Spiel; auch die LCD-How-it-works-Texte am Drucker selbst), 5.0-Generatorliste, Kapitel-5-Titel (13 Generatoren) · **NEU: vier ausführliche Generator-Kapitel** — 5.10 Bausteine (Geometrie-Tabelle: n·8−0,2 Klemm-Maß, hohle Noppen, Unterseiten-Tubes, 45er-Katalog, Workflow), 5.11 Bausatz-Generator (Voxelizer, Support-Filter, Detail-Stufen, Ringwände, BY_LAYER/BY_OBJECT, 800 Teile), 5.12 Figuren (5 Teile, Montage ohne Kleber, 100%-System-Kupplung), 5.13 ColorPic (Band-Prinzip, M600 + LED-Blink, Purge-Turm, Swap/Contrast) · Menü-Referenz (Bricks + ColorPic), Cheat-Sheet (+5 Wege), Makro-Index (+11 Einträge: GEN_BRICKS/BRICK_*/GEN_BRICKKIT/GEN_FIGURES/GEN_COLORPIC/COLORPIC_CREATE) — im PDF gespiegelt inkl. neuer Settings-Zeilen. Batterie: render 1595/1595, Validator sauber, Systemtest 221/0. ||
| .91 | **HOTFIX (.90-Boot-Blocker): `Internal error during connect: Error loading template 'gcode_macro COLORPIC_CREATE:gcode' — no filter named 'endswith'`** — COLORPIC_CREATE prüfte die Bild-Endung mit dem Jinja-Filter `endswith`, den es NICHT gibt (Python-Methode, kein Filter; seit .82 im Paket, aber erst mit dem .90-Update auf dem Drucker angekommen). Fix: Slicing statt Filter — `_cpsrc[-4:] in ('.png', '.jpg') or _cpsrc[-5:] == '.jpeg')`. **Warum die Tests es nicht fingen:** Jinja ≥ 3.1 kompiliert unbekannte Filter STILL (der Fehler kommt erst zur Laufzeit) und ein Render-Durchlauf short-circuited bei `params.X is defined and …` — der R67-Gate lieferte also falsch grün. ** Gehärtet:** (1) der R67-Gate walkt jetzt den Jinja-AST aller 3663 Boot-Templates und prüft jeden Filter-/Test-Namen gegen die realen Jinja-Tabellen — kontextunabhängig, keine Short-Circuit-Lücke; (2) der Config-Validator bekam dieselbe statische Regel (`unknown Jinja filter …`). Beweis: injizierter `endswith` wird von beiden gestellt, das gefixte Muster läuft durch; Sweep über das ganze Paket: kein weiterer Zombie-Filter. Batterie: render 1595/1595 (+5 R130), Validator sauber, Systemtest 221/0. ||
| .90 | **R118–R129: Bricks, Kits & Figuren + Feldlog: Lithophane FLAT druckt in Stufen** — **Bausteine** (Tools > Bricks): Katalog 45 Teile mit exakter Systemgeometrie (Körper n·8−0,2mm — sie klemmen aneinander UND an Originalen, hohle Noppen, Unterseiten-Tubes), Queue wie die Labels, GEN_BRICKS mit CODES wie B2x4:3 und P2x2:2 · **Kit-Generator**: eine geslicte Druckdatei wird zum stilisierten Bausatz — Support/Brim/Skirt/Tower fließen NIE hinein, geschlossene Körper füllen sich, Hohlkörper (Vasen, dünner Infill) werden Ringwände, Detail AUTO/MICRO/SMALL/BIG nach Modellgröße, BY_LAYER = 1 Farbe/Platte = null M600 (der Plattenwechsel IST der Farbwechsel), BY_OBJECT = M600 nur an Farb-Grenzen, max. 800 Teile, jedes Teil eigenes EXCLUDE_OBJECT · **Figuren**: 5 Teile pro Figur, Montage ohne Kleber (Arme schwingen, Kopf dreht, Torso klickt auf den Hüft-Zapfen) — 100% = Originalgröße UND system-echt (Hände greifen Ø4,8-Noppen und Achsen, Hüte sitzen auf der Kopf-Noppe, Füße rasten auf Noppen ein), 25–300% skalierbar · **Feldlog Lithophane**: FLAT druckte ein wellenförmiges Relief (Düse tauchte ins Bild, die Probe verhakte sich) — jetzt Stufen-Druck wie beim Farbbild: Perzentil-Stretch + zuschaltbarer Kontrast-Boost (Skizzen/Logos/Text), levels Graustufen, Stufe 0 = die GESAMTE helle Fläche als saubere Layer (ironbar), jede dunklere Stufe ihre Region, dunkelste = die Konturen; StepL = Layer je Stufe; Farbwechsel AUS / NUR LETZTE Stufe (weißer Körper + schwarze Konturen) / JEDE Stufe; optionaler Bilderrahmen (eckig oder abgerundet) · **Purge-Tower** (12×12mm, 15mm Probe-Freiraum) druckt ab jetzt bei JEDEM Farbwechsel mit (Litho + Farbbild) und nimmt Prime+Wipe nach jedem M600 — PRIME-TOWER getaggt · **Farbbild ColorPic**: Foto flach als Farbbänder hell→dunkel, M600 + LED-Blink am Wechsel, Swap jetzt abschaltbar (Bänder einfarbig), Kontrast-Boost · **Feldlog Rahmen**: Rückseite war 2,4mm GRÖSSER als die Foto-Öffnung (physikalisch nie einführbar) — jetzt Snap-In: Platte mit 0,3mm Spiel durch die Foto-Welle, 4 Wand-Nubs rasten mit 0,2mm Überlappung ein; Foto-Ausschnitt +1,6mm Spiel (echte Fotos laufen ~1mm über Nennmaß); Label-Abstand 6→12mm · **Schnellzugriffe**: Speed/Flow/Accel JE Feature als Listen in Pre-Print UND Live (wie PA per Feature); Z-Hop/PA/PA-smooth/Retract direkt im Live-Root; Fix travel + Fix flow cap + Cap-Wert direkt im Pre-Print-Root; FlowCap-Range 0,5–50mm³/s (High-Flow-Hotends); Travel-Speed direkt einstellbar · **NEU tools/systemtest.py** (Release-Gate): ruft jeden Generator mit mehreren Parameterkombinationen und prüft die gemeinsamen Invarianten aller Ausgaben (TAG, PRINT_START/END, EXCLUDE-Balance, z-monoton außer BY_OBJECT, bekannte TYPES, Bett-Box, keine Sliver-Flut, M600/Turm-Kohärenz) + Verdrahtungs-Sweep (Nonce-Kanäle, GEN-Makros am LCD erreichbar, Modul-Sentinele, Validator) · **Batterie**: render 1590/1590, Audit 77/0, Megatest 144/145/0, Goldens 23/23, Dialekte 13/13, Geometrie- und Textur-Sim grün, Setup-Sim 10/10, Systemtest 221 Checks/27 Dateien/0 FAIL ||
| .89 | **Feldlog .88 Runde 2: Fills drucken zusammenhängend + Ironing folgt dem Top-Winkel** — Einzelscanlines fransen aus, verschmelzen nicht mit den Wänden und drucken Stop-and-Go: **jeder Generator-Fill (First Layer, Bottom, Infill, Top, Ironing) druckt jetzt als EINE durchgehende Zigzag-Kette** — benachbarte Hatch-Linien verbindet eine extrudierte Konnektor-Perle entlang der Border (verschmilzt mit der Wand), Loch-Überquerungen und lange Gaps bleiben rückende Travels (keine Fäden über offene Löcher); Sliver-Linien und degenerierte Links < 0,15 mm werden übersprungen (sonst 400+ Moves/s = MCU-Flut, Audit-Guard) · **Ironing im Top-Winkel**: bügelte früher 90° quer zum Top-Fill, läuft jetzt im selben Winkel (45°/135°, lagenweise alternierend) — glättet MIT der Maserung statt quer · **Label-Queue-Snapshot**: der Font des ersten Jobs färbte auf spätere Jobs derselben Queue ab (globaler Bias) — jeder Job trägt jetzt seinen vollständigen 18-Feld-Snapshot · **4 neue Fonts**: SCRIPT (Dancing Script), HAND (Caveat), PLATE (D-DIN), PIXEL (Press Start 2P) — jetzt 9 Stroke-Fonts · **Shaper-off ehrlich**: ohne `[input_shaper]`-Sektion zeigt das LCD `ShaperOff: n/a` + NOTIFY-Hinweis statt Stille · **Testbatterie**: render 1442/1442 (+9 R117: Ketten-Kontinuität + Winkelgleichheit je Generator), golden re-gefroren (9 Range-Fälle durch Konnektor-Perlen gewachsen, Prozess-Fälle byte-identisch), Audit 57/0, Megatest 143/164/0, Dialects 13/13, Setup-Sim 10/10 ||
| .88 | **hotfix (.87 field log): `Malformed command 'RESPOND MSG="File features: DERIVED by geometry (0% confidence, 23% of moves covered) - no'`** — Klipper cuts EVERY line at the first `;`, even inside quoted strings → the console string ended without its closing quote = malformed (2× per selection of an untagged file). Root causes: 22 messages carried a `;` mid-sentence (`;TYPE:`, tips, info lines), and the DERIVED line's confidence math `{params.CONF|default(70)|int}` turned 0.7 into **0 %** (Jinja `int` truncates floats — the LCD twin already did it right). Fixed: all 22 strings rebuilt without `;` (dashes/commas), DERIVED now shows `(CONF*100)|round|int` = **70 %** · **validator rule R114** (like the R65 `#` rule): a `;` inside any quoted string fails the audit — Jinja `{% … %}` tags exempt (no output line, `|replace(';', '')` stays legal) · render battery 1412/1412 (+3: 70 % math, no `;` in the message, codebase-wide sweep) || | .87 | **hotfix (.86 field log): the `_R2_CONFIG` migration could halt the boot** — a column-0 comment inside the .82-era block (written by our own old setup.sh) stopped the comment-out pattern; the leftover `gcode:` line landed in the previous section → `Option 'gcode' is not valid in section 'board_pins'`, printer halted. Fixed (setup.sh + r2_setup_lib.sh): in-block comments are consumed with a lookahead guard, and the block's trailing newline survives (the rstrip glue bug is fixed too — it could weld the next section header onto a comment line). New setup-sim scenario `r92-config-block` reproduces the exact field layout; proof by negation: the old code fails its checks, the fixed code passes all 10 printer scenarios. **Recovery for hit machines:** restore printer.cfg from the verified `r2_backups/<timestamp>-update/` snapshot, or comment the orphan lines (the Weg-B snippet from the support answer) — after either, update.sh is safe again || .86 | re-tag the stock + the unambiguous retract verdict (R112): **tag v5** — every file tagged before .86 counts as **STALE** (fully functional markers, but the info line predates the .85/.86 keys); **System > File check > RETAG (2×)** upgrades them in place: same LAYER_MARK/APPLY_TYPE count (no double markers), new _FILE_INFO with MAXRATE/SEAM/CFG replay/retract verdict, `.r2bak` backup each, 20 files per run (Pi-friendly), never during a print — the upgrade path is the proven v1→v4 machinery, now also armed for v4 · **Retract verdict** `RETRACT_STATUS=fixed/fw/fix/can` + `RETRACT_MAX=` measured in the file: `FIX!` = Bowden-era retracts that override your tuned values (SHOULD fix), `can` = moderate (optional, for firmware-retraction fans), `fixed`/`fw` = nothing to do — one `Ret:` line in Pre-Print > File, the RetFix offer only appears for fix/can, STALE files show `--` (honest) · **_PREVIEW_SET resets the verdict** on every selection (no stale display between files) · **IRONING_SPACING wired** (was read from slicer headers but never reached the state - found by the new parameter cross-check, now parsed + declared + reset) · **LED_INFO** empty bed-light span reads 'no bed light LEDs' instead of '5-4' (field log .84) · **test battery**: megatest 143 runs / 164 files / +37 hardcore matrix runs + .86 invariants (v5 tag + sane retract verdict on every generated file), setup sim **9 printers** (+Sovol SV06 dual-Z without z_tilt, Voron Switchwire CoreXZ, Prusa-MK4-style hybrid coreXY), render 1409/1409 (+21 R112 + 5 cross-check: all 65 _FILE_INFO keys → declared _STATE vars → reset list, 44 CFG_KEYS → parser, 16 feature codes identical across 07/10/05), golden re-frozen (v5) || .85 | the feature-tagging roadmap §5+§6 (R111): **geometry classifier** for files with NO `;TYPE:` tags — walls per closed-loop nesting, infill per hatch spacing (≥ 3 mm = sparse), bottom/top per layer position; curved paths stay unclassified, bridges are never guessed, tagged files are never classified (the first `;TYPE:` wins) — the file info says so honestly: `DERIVED=1 CONF=0.7 COVER=…` · **modal-Z** layer scan (Z on travel moves counts; Z-hops never fake a layer change) · new measured file keys: **MAXRATE** (max volumetric flow mm³/s), **SEAM/SEAMN** (outer-wall seam position, 5 mm grid, display only) + 14 slicer-config keys replayed (LW_*, ACCEL_SOLID/FIRST/TRAVEL, FIL_DIA, TIME_SLOW, SLOW_MIN, FAN_MIN/MAX) · **two new file fixes**: Fix flow cap (every move over a mm³/s cap gets its F lowered, travels/retracts untouched, idempotent) + Fix travel accel (M204 wraps around travel blocks, print accels stay) — LCD: Pre-Print > File · **feature pressure advance** (SET_FEAT_PA / Live > Features > PA: applied at the feature boundary, global PA returns after; profiled with pre/post) · **fan clamp** (SET_FAN_CLAMP MIN/MAX/BRIDGE + ON: every M106 runs inside the curve, bridge boost while BRIDGE prints — Live > Temps) · **input shaper off per feature** (SET_FEAT_SHAPER_OFF: sharp corners on slow outer walls, freqs saved/restored, PRINT_END + cancel safety net `_FEAT_TUNING_RESTORE`) · **unretract extra** (SET_UNRETRACT_EXTRA: seals the dot after a travel) · profiles carry the new keys (5th element PA, fan clamp, shaper-off — old profiles load with PA=0) · new test: tools/r111_geom_test.py (classifier unit + E2E, hatch-direction bug found & fixed: zigzag lines mapped to one offset now) · dialect corpus +1 family (Simplify3D travel-Z) = 13/13 · renders 1388/1388 || .84 | generator output + per-file profiles (R109): **every generator asks what to do with its file** — Tools > After gen QUEUE (select for printing, replaces the selection when built ON a file: range/texture) or PREVIEW ONLY (just the 3-D preview, nothing queued); sticky + `OUT=` per run; the five generators that never selected (texture, bridge test, resonance plots, plot text/status) now queue properly too · **per-file profiles**: every legacy-printed file remembers its pre-print + live-tuning state — 'post' saved automatically at a successful PRINT_END (cancelled = nothing), 'pre' only manually, auto-load on selection picks the NEWER slot, auto-save never overwrites a manual 'pre' · Pre-Print > Profiles: Material (save without loading first) / Defaults (the 8 standalone profiles) / This file (pre/post, auto toggles) · one apply path (_PROFILE_APPLY) writes values AND ON switches — fixes the old "LOAD_DEFAULT_PRESET set no switches" bug · **R110 hardening round:** setup LED wizard asks the **color order** per chain (GRB/RGB/BGR/RGBW/… with chip table + validation; dotstar + EBB nozzle chain too; GRBG typo removed from printer.cfg.example) · **EOF safety** (legacy [r2_postproc] migration + service install now default NO — an unattended run changes nothing) · **wizard infinite-loop fix** (a stored value outside min/max could dead-end the prompt, setup.sh hung on EOF) · default-profile deletes + file-profile deletes **at the LCD with two-press confirm** (nothing profile-related needs the console) · **setup/update simulation** (tools/r110_setup_sim.py: Ender3 stock/reference, legacy migration, CoreXY 2Z + dotstar, Voron Trident, Voron V2 — install + update + check-mode + EOF + idempotence, sudo-free sandbox) · **slicer/firmware dialect corpus** (tools/r110_gcode_dialects.py: 12 families, 43/43 tagged features = 100 %, layer/marks/FS/FA/idempotency, volumetric detection; fixed Simplify3D "(R)" + "G-Code generated by" detection) · feature-tagging research + roadmap (docs/FEATURE_TAGGING.md) || .83 | field-log .82 issue list — the whole R106 round: **fan wake-up** (0 % → higher now applies the scaled file value immediately, layer-1 hold keeps precedence), honest **velocity/corner hints** (they are CAPS — the visible lever is the cruise ratio), the **user TYPE map** everywhere (visible top layer = Top surface, between = Internal solid, only true airwork = Bridge — the frame front used to tag as Internal solid, so top-surface overrides never reached the visible face; siblings fixed in labels/ties/seal/angles/bridge/Cura-SKIN), **rule ll** (nothing prints unanchored: shelf + disc lips got radial anchor stubs, the kit lips too, the SIDE closure redesigned around the T/B wall anchors), **feature filter** (feature menus hide what the file does not contain — 80 items), presets fill W/H, **frame user presets** (8 slots, save/load/delete at the LCD), **wall loops 1–4**, **Z-hop** on firmware retracts (live + pre-print, absolute Z, layer-change-aware), **travel controls** (SET_LIVE_ACCEL + Velcap relabeled — global caps govern travels too), **lithophane FLAT mode** (bed-clamped, terraced relief, 1–4 color bands with pause/swap), **hard bed clamps** (frame border clamps before splitting; W/H inputs never exceed the build volume), **Z tilt instead of gantry sync** (2+ Z steppers configured → every LCD spot swaps SYNC_GANTRY for a full Z-Tilt submenu: run, probe points, retries 0–5, tolerance 0.005–0.2, boot/print switches), **preheat 182 °C** (filament-swap level — hot enough to change filament while the start dialog waits, still below ooze), **any-Klipper render audit** (bed mesh / vibration / objects / sensor menu items guard themselves on printers without those sections — a permanent test sweeps 993 LCD expressions + 242 macro bodies against a minimal single-Z printer), **LED areas + System > LED Setup** (status / bed work light / nozzle split freely configurable — neopixel or dotstar, mainboard pin or EBB CAN chain, hard-clamped to chain_count, persisted in the new **hardware profile r2_hardware.cfg** — a second variables file that survives deleting variables.cfg), **setup/update wizards** (every hardware value asked in English + double-confirmed: build volume, probe offsets, clean/present positions, LED layout; update asks keep-or-change first), **verified backups + 4 change modes** (backup of every file first, cmp-verified, abort on mismatch; every printer.cfg/moonraker.conf change shown first: automatic with user lines only commented / commented-only / separate txt = safest / skip), **object processing** shown + explained + offered in BOTH directions, **printer.cfg.example fixes** (chain_cnt→chain_count, GRBGR color_order — both halted current Klipper) | · **R115 (.87 field log round 2): start dialog survives long Pre-Print sessions** — Klipper's `idle_timeout` counts from the last *toolhead* move only (the dialog, the preheat and the watcher do not reset it), so `TURN_OFF_HEATERS`+`M84` could fire mid-dialog after a previous print; the dialog now re-arms the countdown from the moment the file is caught (30-min floor, your config value is restored on every way out) and a generator taking over the dialog no longer kills the preheat · **Fan HOLD (Live > Temps)** — the fan entry only *scaled* the file's M106 values, so dynamic slicer fan curves always won; `Hold: X%` (0 = file) *replaces* every M106 of the file at your % (layer-1 fan-off still wins; resets per file) · **Feature PA everywhere** — per-feature pressure advance now also in Pre-Print > Features (16 new inputs), the PA inputs show the *effective* value (explicit or your active global PA), and with a global PA active every feature boundary states the PA it runs at instead of silently showing 0 · **Frame first layer see-through** — loading a pre-R101 frame preset wrote `frame_bot_l=0` (undefined|int=0) = sparse infill from layer 1; the load now defaults to 2 solid layers and FRAME_INFO shows 'bottom solid N layers' · **PAUSE NOW hardened** — it was the FIRST entry of Pause & Control, an encoder double-click fired it instantly ('constantly quick-pauses'); harmless entries first + two-press confirm (AGAIN! pattern) ||
| .82 | critical config fix (field log .81): the R92-onward bed/position carrier was a raw `[r2_postproc]` section in printer.cfg — **Klipper refuses unknown sections** („Section 'r2_postproc' is not a valid config section"), so the printer ended up in a halt loop the first time the section was really written (setup.sh offer). The carrier is now a KAMP-style **`[gcode_macro _R2_CONFIG]`** settings macro (`variable_bed_min_x` … , `variable_present_x/y`, `variable_wipe_x/y`) — valid for Klipper, native for the macros, parsed by the watcher; `setup.sh` migrates legacy sections automatically (backup + values kept); the same field log also uncovered the first-halt mechanism: appending after the `#*# <save_config>` block made the autosave unreadable („modifications after header" → „Option 'control' in section 'heater_bed' must be specified") — inserts now always go before that block |
| .81 | honest host verdict + portability hardening (field log .80): HOST_CHECK's swap verdict now measures swap **activity** (vmstat in/out) — 109 MB of quietly parked pages after boot were flagged „SWAPPING!" with an error sound on every check although the Pi was healthy (stable swap, no load, no throttle); quiet pages now read as OK with a calm explanation, only real swap traffic stays loud. Compatibility fixes from the portability audit: PRINT_END's part presentation had a fixed Y228 (a crash on any bed under ~232 mm) — now clamped to the axes and configurable (`[r2_postproc] present_x/present_y`), both calibration-tower end parks (fixed Y190) and the PLT_FRAME park are clamped, the nozzle-wipe pad anchor is configurable (`wipe_x/wipe_y`), and `megatest.py` accepts `--bed=x0,y0,x1,y1` / `--cfg=printer.cfg` to sweep another printer's bed (too-big combos count as SKIP — the generators correctly reject them); `setup.sh` (environment wizard: service, KAMP, LED effects, RAM hogs, swap tuning) and `COMPATIBILITY.md` (portability report) join the package |
| .80 | megatest hardening (field log .79): a 101-run sweep over every generator at its parameter extremes found and fixed two real bugs — the plotter DRAW mode scaled small images past the bed (48px drawing → y up to +1500 mm; big photos silently squashed to ~72 mm) and every frame file tags the shelf bands as BRIDGE but TYPES never listed it on normal frames; plot output now carries a final bed guard too; `tools/megatest.py` joins the package (rerun any time: `python3 tools/megatest.py`) |
| .79 | frame shells, sparse infill & travel order (field log .78): Top/Bottom solid layers settable (independent of front effect and orientation; default bottom skin 2) · body infill down to 5 % (was 20) with its own INFILL-SPARSE feature tag · ring fill travels stay INSIDE the band now — the scanline order used to cross the photo opening on every line (139 long retracted travels per body layer → ~5, layer 1: 146 travels → 6), faster and no fuzz at the edges · TYPES lists only features the file really tags (SURFACE-TOP only for structured fronts / FLIP skin) |
| .78 | plain uploads convert ONCE (field log .77): a plain image/text in the gcodes folder (AxtBunny.png) was re-converted to pen-plotter g-code on EVERY watcher (re)start — “1 processed” at every boot, the .gcode rewritten, its preview push racing the Klipper restart after an update (HTTP 404); the “already converted” check now reads the OUTPUT file, and a 404 preview push says Klipper is probably still restarting |
| .77 | generator file info + label modes (field log .75): frame / cable-tie / angle files carry _FILE_INFO with TYPES now — the Pre-Print file info and the feature activators work for EVERY generated file (they were empty: generated files are TAGged, the scan never adds them); structured frame fronts tag SURFACE-TOP instead of CUSTOM; labels get two clear modes — GROW (the label grows to the text, W/H are minimums and Calc fit sets the needed size as the W/H lower limits) and FIXED (the label stays W/H, the font scales into it) — and the confusing "Preview fit?" item is now "Calc fit" with a plain explanation |
| .76 | watcher start-up (field log .75): the first scan after a boot/restart runs in time-boxed chunks now — it used to block the watch loop as ONE pass (12+ minutes on a swapping Pi Zero right after a reboot) and every file selected in that window showed an empty file info; selections are serviced within seconds while the start backlog drains in the background · a backlog preview push can never overwrite a fresher file selection anymore (preview nonce re-check before the push) |
| .75 | frame placement & first layer (field log .74): every frame plate — one-piece, multi Part A/B, split kit — sits centered on the usable bed, nothing prints at the x0/y0 corner anymore (the multi-plate stand sat at the raw bed origin half off the bed, the one-piece stand overlapped the ring — both placement bugs fixed); the first layer of every frame part prints brim → inner wall → outer wall → ONE continuous zigzag fill with extruded connectors (single hatch lines curled up at their ends and frayed the borders), open holes are crossed only with a retraction · retract keep-outs completed (field log .74): cable-tie head channel + loop slot, gasket groove, backplate keyhole + stud holes and the bridge-test spans are registered keep-outs too — no travel crosses an open hole without retracting anymore (was 74+22+17+1 unretracted crossings; zero-length travels never retract; FLAT gaskets and lithophanes have no openings at all) |
| .74 | range feature truth (field log .73: vase opens with the cut feature instead of the raft type, brim prints on the FIRST layer inside raft layer 1, TYPES/FS/FA describe the EXCERPT not the whole source) · full slicer feature census 12 → 16 (field log .74: overhang wall, internal bridge, prime tower and custom G-code sections are now real, editable features; small-perimeter speed/accel from the config header visible in the file info; every slicer family's `;TYPE:` dialect mapped — see the census table in ch. 3) · old default presets keep loading (new features fall back to OFF) · range hole quality (field log .74): the cap hole prints bridges AROUND the opening first, the hole ring sits ON the bridges, the solid fills up to the edge — no sagged ring, no bridge to pick out, the hole stays open; every generator (labels, angles, frames) retracts travels over open holes at ANY length (screws/label holes, frame view opening as polygon keep-out) · beep discipline while printing (confirmation/feedback beeps silent during an active print — no more purge blobs from micro pauses; critical sounds always play) · seamless texture on arc-fitted files (G2/G3 outer walls flattened into textured chords, E exactly preserved — vases get the texture all around, not just in the corners; fuzzy presets sized after OrcaSlicer: ORCA/Hide layers/Subtle/Grip, thickness 0.05–1.5 mm) |
| .73 | frame & display-case generator (real-bed fit: one file / multi-plate Part A+B / 4-strip glue kit, RECT/OVAL, BACK bayonet - SIDE slide-in, hang keyhole + easel stand, surface Lines/Waves/Honeycomb/FLIP, disc insert glass/plexi/foil/litho, hidden cable duct), texture tool for ANY g-code file (fuzzy skin + GRID/WAVES/HEX/MANDELBROT bumps on outer walls only - tags/E/Z/F untouched, _TX result never auto-started), file check (tag version census on LCD/console/SSH + safe retag with .r2bak backup), seal + lithophane generators with LCD image browser, cable-tie redesign CLASSIC/LOOP, real-bed truth via [r2_postproc], probe-safe color-change purge strip, global x feature parameter model (flow multiplies, accel percent scaler), Tools menu English, live-tuning menu regrouped (audit), nozzle diameter from printer.cfg for every generator, prime-line de-ooze + resume without object purge (field log .73) |
| .72 | field-log .71 fixes: EXCLUDE_OBJECT POLYGON as valid json (cable ties + angles/plates start crash; all 5 generators verified), global speed/accel no longer eat feature overrides (feature rides ON TOP of the global, re-applied on every change; feature accel beats the global), range holes print as ONE spiral boss with retracting travels (no more strings over the hole), APPLY_TYPE re-derived from ;TYPE: when a source carries none (everything-printed-as-solid-infill mitigation), hole diameter clamps to the REAL section outline + 2mm margin (boss never sticks out of L/round sections) |
| .71 | LCD declutter: the four part generators (Kabelbinder, Winkel+Flach, Labels, Plotter) now live in ONE 'Tools' top-level menu — the root drops from 10 to 7 entries; guards unchanged (a missing module include hides its entry), console paths + manual follow |
| .70 | part generators (cable ties + angles/flat connectors, LCD top menus), centered layer-range holes: floor hole with boss ring (E14/E27 presets) + bridge-first top hole, angle walls/infill/ironing (+ inner-wall fix), nozzle LED split for the EBB42 (SET_NOZZLE_SPLIT), slicing guide for any slicer, electronics chapter: U2C V2.1 + EBB42 CAN + 230 V relay (wiring lists, firmware, safety) |
| .69 | file fixes IN PLACE (no re-upload): Pre-Print > File > RetFix file rewrites the selected file's retract pairs to G10/G11 on disk (markers survive), Vol->mm fix converts Marlin-volumetric E to mm (idempotent, beeps at start + done), start dialog auto-released; ~100 ms micro-pauses between multi-value disk writes (idle only) |
| .68 | file info shows the slicer + firmware flavor of every file (Orca/Prusa/Cura/Elegoo/Kiri:Moto/AstroPrint/SliceBeam … for Klipper/Marlin), loud warning on Marlin-volumetric files (Klipper counts E in mm), RetFix: old Bowden-era files re-uploaded with retracts rewritten to G10/G11 (current retraction applies, live-tunable) |
| .67 | print-start killer fixed (feature lists + material saves survive Klipper's command parser), generated files sort to the top (00_…_V version suffix, same name overwrites), label quality (glyph retracts, stroke ≤ cap/5, purge tower 15 mm on the probe-safe side), real fit preview on the LCD, labels up to 5 lines / near-bed size, filament stat in meters, SAVE+RESTART restarts when nothing is pending |
| .66 | user-handbook manual + PDF (scenarios, generators, calibration ladder); three small-text label fonts (COND/NARROW/CAPS); maintenance menu in calibration order |
| .65 | postproc streaming: range generation + upload tagging no longer load whole files into RAM (32 MB source → Pi-safe memory), byte-identical outputs (golden test added) |
| .64 | start-killer fixed (list literals with spaces broke SET_GCODE_VARIABLE), labels auto-fit/auto-grow instead of errors, All-OFF removed |
| .63 | generator files auto-select themselves, range OUTLINE floor fills the enclosed area, L1/L2 rules in every mode, live-tuning clarity (PARAM_SOURCES, FeatSpd) |
| .62 | (field round: MCU shutdowns solved host-side) |
| .61 | cold pull back to Maintenance, filament menu before the print |
| .59/.60 | mesh travel cap · live file/feature mirrors, FeatOn/FeatSpd rework |
| .58 | plotter top-level menu, 3 label lines, range clamping + PRINT_END + file info at top, uniform letter scale |
| .55–.57 | label maker (LCD text editor, fonts, holes, two colors), range floor/brim/top with OUTLINE shapes |
| .53 | KAMP object data kept for adaptive mesh (field fix) |
| .48 | resonance diagram print/plot + shaper apply, dark-background plots, plot text/status, bridging test |
| .47 | label system, save-config warning |
| .45 | generated calibration files: temp tower, flow cube, retract tower — no sliced file needed |
| .44 | per-feature speeds/accels MEASURED from the g-code (FS_*/FA_*), TYPES= |
| .43 | 12-feature override system, one global speed factor |
| .42 | APPLY_TYPE injection after every ;TYPE: |
| .40/.41 | live tuning reads REAL Klipper values, flow calibration, temp tower bands, ironing cal |
| .38/.39 | gapless legacy resume, purge/anti-ooze chain, one takeover mode |
| .34–.37 | universal print intercept (hold at position 0), net probe, nozzle wipe |
| .29–.33 | probe-safe prime line, legacy start takeover, anti-ooze standby |
| .24–.28 | bed mesh strategy, KAMP integration, parking/homing guards |
| .10–.23 | foundation: state machine, watcher, start dialog, materials, sounds, LEDs, LCD menus |
