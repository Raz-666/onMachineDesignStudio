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
5. [The generators: Range, Labels & Plotter](#5-the-generators-range-labels--plotter)
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
25. [Complete macro index — all macros with parameters](#25-complete-macro-index)

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
`_FILE_INFO` is replayed to the system: Pre-Print > File (G-code) immediately
shows THAT file's values — material, layers, speeds, features — never
leftovers from the previous print.

**What the selection preview tells you** (Pre-Print > File, same data as the
Live > File panel):

| Field | Meaning |
|---|---|
| Type | MARKED (fully tagged) / LEGACY (no markers) / PLOT (pen file) |
| Sliced by | R84: the slicer + version and the firmware flavor the file was made for (OrcaSlicer, PrusaSlicer, Cura, Elegoo, Kiri:Moto, AstroPrint, SliceBeam, … for Klipper / Marlin) — works for fresh uploads AND foreign downloads |
| Material, layer height × count, line width, flow ratio | straight from the slicer header |
| By-object | sequential printing detected (several objects, Z falls) |
| TYPES= | which features the file really contains (walls, infill, supports …) |

**Two file quirks the system flags and FIXES for you — in place, no
re-upload (R84/R85):**

- **Marlin-volumetric files** (`;FLAVOR:Marlin (Volumetric)`, e.g. from Cura):
  they count E in mm³ — Klipper expects mm and would print them heavily
  under-extruded. The file info shows the warning and the print start says it
  out loud (alarm + M117). **Pre-Print > File > `Vol->mm fix`** converts the
  file directly: every E value (including G92) is divided by the filament
  cross-section (1.75 mm → 2.405 mm²), the volumetric markers are neutralized
  and a conversion note lands in the header. R2-D2 beeps at the start and
  plays the happy tune when the file is Klipper-ready (then simply select it
  anew). Idempotent — a converted file is never converted twice.
- **Old Bowden-era files** with long baked-in retracts (5–6 mm where your
  direct extruder wants ~0.8): select the file, then **Pre-Print > File >
  `RetFix file`** — the watcher rewrites the file ON DISK: clean
  retract/unretract pairs become **G10/G11** (firmware retraction), so your
  CURRENT retraction applies — live-tunable during the print. The R2 markers
  survive (no re-processing needed), wipes and folded retracts stay
  untouched, start beep + done beep, and the console reports the pair count.
  If a start dialog holds the file it is released automatically first. For
  future uploads you can instead leave **Pre-Print > RetFix ON** — every new
  upload gets the treatment automatically.

**Click pacing (R85):** actions that write many values at once (material
select, preset load/save, range create, file fixes) insert ~100 ms
micro-pauses between the disk writes — the Pi Zero never faces a write burst.
While a print runs the pauses no-op (a dwell would stutter motion).
| FS_* / FA_* | the MEASURED original speed / acceleration of each feature |
| L1/L2 temps, PA, retraction, fan, nozzle, wall loops | everything Pre-Print can override |

### 3.2 What the tools do with every file — the flow

```
upload / copy / scp ──►  gcodes folder
                              │  r2_postproc.py (service, 1 s)
                              ├─ G-code ──► tagged in place: LAYER_MARK,
                              │             APPLY_TYPE, _FILE_INFO, TYPES/FS/FA
                              ├─ name.png.gcode / .jpg / .svg / .pdf / .txt
                              │        ──► converted in place to a pen-plot file
                              └─ generated later on demand (00_ = top of
                                  the list, _V = your version number):
                                  Range 00_<src>_L<a>-<b>_V<xx>.gcode
                                  Label 00_<text>_V<xx>.gcode
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
| File (G-code) | full slicer summary of the SELECTED file (type, material, layers, speeds, accels, temps, PA, retraction) + 12 feature activator rows: each shows the file's real speed and an ON switch — features the file does not contain show 'n/a' and refuse |
| Material | LOAD NOW + all material values (Bed/Hotend L1/L2, PA + smooth, flow, retract, fan L2) + Save as preset — edits of the ACTIVE material apply live |
| Temperatures | Bed/Hotend L1/L2 + Fan L2 (ON/OFF each) + the file's own values for comparison |
| Motion | PA (+smooth), retraction length/speed/unretract, acceleration, velocity, minimum cruise ratio, square corner (ON/OFF each) |
| Features | 12 submenus, one per feature (outer/inner wall, sparse/solid infill, top/bottom surface, bridge, gap fill, support, ironing, skirt, brim): file original + ON switch + speed % + accel each |
| Flow / 1st layer | global flow (1–300 %) and first-layer speed (0 = off, default 75 %) |
| Bed Mesh | Level old files · Mesh ON/AUTO/OFF · Save after · Adaptive · Travel cap while meshing · Calibrate now · Load…/Delete… |
| Range/Stop | planned end at layer N + the range generator (ch. 5.1) |
| Filament | Load / Unload / Change (M600) before the print, load & unload lengths |

**The golden rule:** overrides only apply when they are ON. A stored value
without ON never touches the print; the file rules until you switch something
on.

### 3.5 The start dialog — AS LEGACY or AS SLICED

Every print start (print button, LCD list, PRINT_START) stops at the dialog:

| Mode | LCD / console | What rules |
|---|---|---|
| **AS SLICED** | > PRINT AS SLICED · `PRINT_AS_SLICED` | the FILE, truly 1:1 — no overrides, no first-layer brake beyond the L1/L2 rules, no sequential restarts. Live commands still apply. The first-layer rules (material L1/L2 temps, fan off on layer 1) stay on even here — toggle with Pre-Print > Temps > L1 rules |
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

- **Live Tuning > Speeds** — global % and the CURRENT feature's % (the display
  names the feature that is printing right now)
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

## 4. Scenario library — every file type walked through

Real situations, start to finish. Each scenario lists the clicks and what the
system does in the background.

**Scenario A — correctly sliced, print by layer (the normal case)**
Slice with the R2 profile (the post-processing script is optional — the service
tags the file anyway). Upload → select → start dialog → **AS LEGACY**.
Homing, bed temp, adaptive mesh, nozzle wipe, purge, then layer 1 with L1
temps, fan off and the first-layer brake; at layer 2: L2 temps, the file's fan
value, 100 % speed. Feature overrides (speed/accel per feature) work because
the file carries `APPLY_TYPE` markers.
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
Z tracker counts layers — layer 2 brings L2 temps + fan + 100 %. File M104/M220
are redirected layer-strictly. **AS SLICED** = the file rules 1:1 — its own
start gcode runs, nothing is injected (live tuning stays available).

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
1. Labels > Text: pick line 1–3, position, rotate to the character, click —
   the text assembles live on the display.
2. Labels > Settings: size (default 50×15), font (SMOOTH / MONO / COND /
   NARROW / CAPS), hole side + diameter, stroke = letter line width.
3. Job > Add label — repeat for several DIFFERENT labels (queue shows n/24).
4. Job > Create — the watcher builds `00_<text>_V<xx>.gcode` and beeps.
5. Start it like any file. Two colors: print pauses with M600 after all base
   plates — load color 2, RESUME purges into the purge tower, the text goes
   on top. Every label is an exclude object (skip single labels live).
Details: ch. 5.2.

**Scenario I — plotting an image (pen instead of nozzle)**
1. Mount a pen (Plotter > Pen offset X/Y/Z tells the system where it sits).
2. Upload `bild.png.gcode` (or .jpg/.svg/.pdf/.txt) — the converter replaces
   the file in place with pen G-code; auto-contrast finds the ink on any paper
   tint, dark boards invert automatically.
3. Select the file → start dialog (a plot file: AS SLICED = pure pen run,
   AS LEGACY heats only if the extruder is ON).
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

## 5. The generators: Range, Labels & Plotter

Three generators turn the printer into a manufacturing tool of its own: partial
prints from any G-code, label plates from typed text, pen plots from images.
All of them write normal G-code files into the gcodes folder (the watcher
picks them up), all of them run through the NORMAL start flow, and all
generated objects are exclude-objects (skippable live).

### 5.1 Range — print a section of an existing file

Perfect for re-printing a broken section, testing the critical middle of a
long print, or making a part from just a few layers. Find it in
**Pre-Print > Range/Stop** (the planned stop-at-layer lives in the same menu;
Live > Pause & Control has the Stop@ shortcut).

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
- its own `_FILE_INFO` at the TOP — Live > File shows the excerpt's values
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

**Brim — loops around the start (0–10)**

N loops around the raft/section outline, zero gap — the first loop's inner
edge touches the model wall. Key-ring style adhesion helper.

**Notes**

- The generated raft counts as INFILL-SOLID, the brim as BRIM — feature
  overrides (speed/accel/flow) work on the generated geometry like on any
  sliced section.
- The excerpt's layer 1 = always 0.2 mm high, whatever the source layer
  height; following layers keep the source spacing.
- Every parameter is also available per console:
  `SET_LAYER_RANGE FROM=125 TO=225 FLOOR=5 FLOOR_SHAPE=OUTLINE FLOOR_FILL=SOLID TOP=2 BRIM=4 CREATE=1`
- E and Z of the body are shifted so the section prints as a standalone part
  in the file's own extrusion mode (relative or absolute E — both work).
- Works with any tagged source file, including multi-object files (EXCLUDE
  handling cleans up cut artifacts at the section borders).

**Stop@ — the planned normal end**

**Stop@ N** (Pre-Print > Range/Stop, or Live > Pause & Control) ends the print
NORMALLY when layer N begins — stats, fanfare, cooldown, like a finished
print, not a cancel. The natural partner for "print only the first 50 layers".

### 5.2 Labels — the built-in label maker

Name tags, key fobs, drawer labels, cable markers — engraved text, no slicer,
entirely from the LCD (or one console line).

**The workflow**

1. **Labels > Text**: up to **5 lines per label** — pick the line (1–5),
   pick the position (Pos 1–N), rotate to the character (Chr), click. A–Z a–z
   0–9 space ÄÖÜäöüß and the common symbols are available; the text prints
   correctly even where the 12864 display can only hint at umlauts. Only
   FILLED lines print — one line simply centers in the free area.
2. **Labels > Settings**: size, font, stroke, layers, hole … (table below).
3. **Job > Add label** — repeat Text+Add for several DIFFERENT labels (same
   text twice = two identical plates). The queue shows n/24.
4. **Job > Create** — the watcher generates `00_<text>_V<xx>.gcode` (beeps
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
| Vers | V01–V09 | the version in every generated file name. Same text + same version = the file replaces itself; bump the version to keep an iteration |
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
**Fit preview (Labels > Settings > `Preview fit?`):** answers with the REAL
numbers the generator will print — final label size including growth, cap
height, effective stroke, ~characters per line, and for a fixed Size the
MINIMUM label size it needs (e.g. `for 12mm caps make the label >= 228x17mm`),
plus warnings (stroke capped, purge tower does not fit, plate exceeds the
bed). The LCD keeps the short form (e.g. `80x17+ 3.7`). The instant estimate
in Labels > Text is a rough guess — the exact numbers follow ~2 s later in
the console.

**Console one-liner (everything optional):**

```
GEN_LABELS TEXT="WERKSTATT~KELLER|VASE" W=60 H=30 FONT=COND SIZE=8 SPACING=1 LINES=2 HOLE=LEFT HOLE_D=5
```

(`~` = line break within a label; `|` separates several labels of one job)

### 5.3 Plotter — images, photos and text with a pen

Mount a pen instead of (or next to) the nozzle and plot images, photos,
vector graphics or text — no slicer involved.

**Files — the name is the switch**

| Upload as | What happens |
|---|---|
| `name.png.gcode` | PNG → pen lines in place |
| `foto.jpg.gcode` | JPEG (baseline; progressive photos refuse — export as PNG) |
| `drawing.svg.gcode` | SVG vector graphics |
| `plan.pdf.gcode` | vector PDF |
| `notes.txt` (or `name.txt.gcode`) | text → auto-wrapping, auto-shrinking page |
| options in the name | `bild.c3.s035.png.gcode` = 3 shades, 0.35 mm hatch (defaults c2 / s040) |

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
- **Status on paper**: Plotter > **> Plot status** (`PLOT_STATUS`) draws the
  SHOW_STATUS report — version, mode, material, temps, PA, flow, speed, accel,
  input shaper, mesh, active overrides — on one page.

**Plotter menu (top level)**

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

## 6. During the print: tuning, pauses, objects

Everything that happens between "print started" and "print finished". Live
tuning works in EVERY start mode — including AS SLICED and while plotting.

### 6.1 Live tuning reference

```
Speeds:  SET_GLOBAL_SPEED PERCENT=20..300 (never capped) — ONE global factor
Feature: SET_OVERRIDE_VALUE NAME=feat_spd_<code> VALUE= · NAME=feat_acc_<code> VALUE= · NAME=feat_on_<code> VALUE=1|0
         (12 feature codes) · SET_IRONING_FLOW PERCENT=
Accel:   SET_GLOBAL_ACCEL ACCEL= — the global accel
Limits:  SET_LIVE_VELOCITY VELOCITY= · SET_LIVE_MINIMUM_CRUISE_RATIO VALUE= (each confirms "[OK] … -> Klipper") ·
         SET_LIVE_SQUARE_CORNER VALUE=
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

**One global factor.** LCD > Live Tuning > Speeds/Accels has exactly one
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
`SKIP_OBJECT OBJECT=name`, 2× confirm — `SKIP_CURRENT_OBJECT` skips the one
printing right now, `SKIP_DISARM` cancels a pending skip, `SHOW_OBJECTS`
lists all objects with their state). The rest of the print continues; KAMP's
adaptive mesh and the smart parking already know the remaining objects. Works
for sliced multi-object files AND for generated files (labels, ranges,
bridging towers — every generated part is an exclude object).

**End the print normally at a planned layer:** Pre-Print > Range/Stop >
**Stop@ N** (or Live > Pause & Control > Stop@) — when layer N begins, the
print ends like a FINISHED print: park, stats, fanfare, cooldown — not a
cancel. Combined with the range generator (ch. 5.1) this covers "print only
part of it" in both directions: from the file start up to N, or a standalone
section From–To.

## 7. Filament: load / unload / change / runout / cold pull

- temperatures always right: print temp kept during prints; idle heats ≥200 °C
- load_length 60 mm (LCD 20-150) feeds LOAD_FILAMENT · unload_length 90 mm
  (LCD 40-150) feeds unload AND change — both settable - PURGE_MORE purges another 15 mm during a change
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
  Priority: override ON > file > preset.
- purge + layer 1 = L1 (the start paths heat the hotend to the L1 value for the purge)
- file M104/M109/M140/M190 redirected strictly BY LAYER — layer 1 → L1, ≥2 → L2
  (both takeover modes; AS SLICED passes 1:1)
- layer 2 = L2 — switched by LAYER_MARK (marked) or the Z tracker (legacy / AS
  LEGACY), identical values
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

**Global = the ONE overall regulator:** Global Speed % (LCD, L1 brake,
file M220) scales EVERY speed in relation — stored clean as `g_speed_clean`,
never multiplied by anything else. **Per-feature values sit ON TOP of the clean
global value and never change it**: Feature speed = percent x global (e.g.
global 80 + wall 80 -> wall segments run at 64, the next feature is back at
80 — no decay). Feature accel is absolute (mm/s²) and replaces the file's M204
while that feature prints.

**Why the redesign (field log):** the old
APPLY_TYPE ran through the M220 interceptor — 75% brake x 80% wall multiplied
on the ALREADY scaled factor, feature by feature: 75x80 -> 60 -> 48 -> ... ->
19%. Since then feature values go straight to Klipper via the BASE commands
(M99220/M99221/M99204) — the interceptor (and with it the global value) is
never touched by a feature.

**12 features:** outer/inner wall, sparse/solid infill, top/bottom
surface, bridge, gap fill, support, ironing (+own flow), skirt, brim — every
one with its OWN ON switch + speed % + accel (Pre-Print > Features, one
submenu each; Live Tuning shows the CURRENTLY printing feature as "Cur:" —
or "CurOv:" to toggle its override live). Post-processor v4 maps Orca types
including Custom/Skirt/Brim and treats Gap infill as its own type GAPS.

**Originals, availability & OFF-reset:** the post-processor MEASURES the
real values from the g-code itself — the most frequent F value per feature
segment (= its speed in mm/s) and the M204 in effect there (= its accel).
They are shown everywhere (File > File: rows, each feature's "File:" line)
and they are what "OFF" returns to: switching a feature override OFF resets
the stored speed to 100% (= 1:1 with the file × global) and the stored accel
to the file's M204 (0 if the file sends none). Only features that really
occur in the file are editable — the activator rows of absent features show
"n/a" and every input refuses with "not in this file" (unknown/legacy files
without TYPES data stay fully editable as before).

**Machine limits**

| Parameter | Override (Pre-Print > Motion) | Live command | Klipper setting |
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
`PID_TUNE_HOTEND FAN=…` / `PID_TUNE_BED`.

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

**Z Gantry Sync** — re-syncs both Z motors to a common zero (SET_KINEMATIC
POSITION via [force_move]); toggles for boot and print start. Run it after
mechanical work on the gantry or when the X gantry visibly tilts.

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

Eight top groups — in LCD order: **Start Print?** (appears in the waiting
state, position 1), **Live Tuning** (during a print, position 2), then
Pre-Print, **Labels**, **Plotter**, Quick Macros, Maintenance, System. Start
dialog and live tuning sit right at the top. Every line fits the 16 characters
of the 12864 display — the value you edit is always visible (test-enforced).
Pattern: first line = ON/OFF toggle (value stays stored), then the values.

**Live Tuning (during a print, every mode)** — shows Klipper's REAL values:
the flow input reads the actual extrude factor (M221), PA reads
`pressure_advance`, smooth reads `smooth_time`, accel reads `max_accel`,
retraction reads the firmware values — what you see is what runs.

| Entry | Contents |
|---|---|
| Z +0.04 / +0.12 / −0.04 / −0.12 | babystepping right at the top |
| Hot / Bed / Fan / Zoff | cockpit: temperatures, fan %, Z-offset display |
| Speeds | Global % (THE overall regulator) + FeatSpd: the currently printing feature's % + FeatOn: its ON switch + Src info (file/overwrite/live) + "Now:" which feature is printing |
| Accels | Global mm/s² + FeatAcc: the currently printing feature's accel |
| Features | 12 submenus = same as Pre-Print > Features, but live: edits re-apply immediately when that feature is printing |
| File (G-code) | FULL mirror of the Pre-Print file info: measured originals (speed/accel per feature), 12 click-activators, temps, PA, retraction, fan, flow — everything during the print |
| Extrusion | Flow % (1–300), PA, PA smooth, RetLen / RetSpd / Unret, Ironing flow — every input shows what Klipper REALLY runs right now, Src info shows file/overwrite/live |
| Velocity | max velocity · minimum cruise ratio · square corner — live, like Mainsail |
| Plotter | while plotting: pen speed %, pen Z ±0.05, X/Y ±0.5 shifts |
| Pause & Control | pause now / next layer / at layer / Stop@ (planned NORMAL end) / M600 / Filament (Load/Unload/Change while paused) / cancel (2×) |
| Objects | skip single objects (2× confirm) |
| Sources | PARAM_SOURCES: provenance of every parameter (ch. 14.1) |

**Pre-Print**

| Entry | Contents |
|---|---|
| File (G-code) | full slicer summary of the selected file (type, material, layer height × layers, line widths, flow ratio, by-object, nozzle × wall loops, ALL speeds, accels, L1/L2 temps, PA, retraction) + **sliced by <slicer> for <firmware>** (volumetric files get a loud warning) — shown from the MOMENT you select the file; the per-feature values are MEASURED from the g-code — PLUS 12 activator rows (OW…BM): each shows the file's REAL speed + o:ON state; CLICK toggles that feature's override; features NOT in the file show 'n/a' and refuse |
| Material | LOAD NOW + all material values + Save as preset — editing a value of the ACTIVE material applies LIVE too |
| Temperatures | Bed L1/L2, Hotend L1/L2, Fan L2 (ON/OFF each) + File H:/File B: = the file's own values |
| Motion | PA (+smooth), retraction len/spd/unretract, Accel + Vel + MCR + Corner (ON/OFF each) + File R: |
| Features | 12 submenus: outer/inner wall, sparse/solid infill, top/bottom surface, bridge, gap fill, support, ironing (+flow), skirt, brim — each shows the file's ORIGINAL (File:) + own ON switch + speed % (× global) + accel; only features the file really contains are editable; switching OFF resets the stored values to the file original — never touches the global values |
| Flow / 1st layer | global flow (1–300 %) · first-layer speed % (0 = off, default 75) |
| Bed Mesh | Level old files · Mesh ON/AUTO/OFF · Save after · Adaptive · Travel cap · Calibrate now · Load…/Delete… |
| Range/Stop | Stop@ layer + From/To (capped to the selected file's layer count!) + Floor/Top (each FOOTPRINT or OUTLINE, each GRID or SOLID fill) + Brim + Create excerpt (ch. C.1) |
| Filament | Load / Load length / Unload / Unload length / Change (M600) — available BEFORE the print too |
| RetFix | ON/OFF — auto-treats every NEW upload's clean retract pairs into G10/G11 (old Bowden-era files); for the SELECTED file use Pre-Print > File > RetFix file instead (in place, no re-upload) |
| File fixes (in File menu) | RetFix file + Vol->mm fix — repair the SELECTED file directly on disk (start beep + done beep, markers survive) |

**Labels**

| Entry | Contents |
|---|---|
| Text | L1–L5 pickers · Show text · Pos 1–12 (cursor) · Chr (rotates A–Z a–z 0–9 space ÄÖÜäöüß and symbols) · Delete char · Clear text — the current text appears on the LCD with the cursor position; Fit gives a rough estimate, the exact preview follows ~2 s later |
| Settings | W/H (label size, default 50×15) · Font: SMOOTH / MONO / COND / NARROW / CAPS (the * marks the active one) · Lines 1–3 · Size (0 = auto) · Spc letter spacing · Stroke = letter line width (0 = auto, 0.6 = nozzle) · Base/Text layers · LH / 1st · Ironing · Hole NONE/LEFT/RIGHT/TOP/BOTTOM · Hole D · Brim · 2 colors · Gap (grid spacing) |
| Job | Queue n/24 · Add label · Del last · Clear all (2×) · Create (beeps) · Fit (how many fit the bed) · How it works |
| Settings | W/H · Lines 1–5 · Size (auto or cap mm) · Spc · Base/Text layers · LH/1st · Ironing · Hole · Stroke · **Vers V01–V09** · **Preview fit?** (real numbers incl. growth + minimum size for a fixed font) |

**Plotter** (top level) — DRAW/DOTS, dot gap, pen offset X/Y/Z, scale X/Y %,
bed corner limits, extruder ON/OFF, Z up/down, speeds, max size, auto-
contrast, Invert AUTO/ON/OFF, Drive frame test, Start (overrides), Plot text
file, > Plot status. All baked into the file at conversion time; live entries
while plotting (ch. C.3).

**Maintenance — in calibration order** (the ladder, ch. 9):

**PID Tuning** (hotend+fan% / bed) → **Leveling** (Z offset, bed screws) →
**Bed Mesh** (settings + profiles) → **Extruder Cal.** (E-steps) →
**Vibration Cal.** (shaper calibration, diagram print/plot, apply result) →
**Temp Tower** (band control + generated tower) → **PA Cal.** (line test +
**PA Smooth Cal.**) → **Flow Cal.** (generated cube + calculator) →
**Retract Tower** (generated) → **Bridging** (generated) → **Ironing Cal.**
(cards) → **Clean Nozzle** → **Filament** (load/unload/cold pull) →
**Z Gantry Sync** → **KAMP** → **Tests** (LED/sound/self test/status).

**Macros (Quick Macros):** load/unload, gantry sync, status, sounds on/off,
LEDs on/off, Nozzle LED — mode AUTO/ON/OFF + live brightness + live color
R/G/B + presets.

**System:** restarts (2×), Pi shutdown (2×), **Force end print**, save config
(2×, warns that the LCD goes dark), status.

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
| Per feature | feat_spd_<code> + feat_acc_<code> + feat_on_<code> for 12 codes (wallouter, wallinner, infillsparse, infillsolid, surfacetop, surfacebottom, bridge, gaps, support, ironing, skirt, brim); ironing + ironing_flow | 100 · 0 each | only while that feature prints (APPLY_TYPE): speed = % x CLEAN global, accel absolute — the global value itself never changes; feat_on=0 RESETS the values to the file original; unavailable features refuse |

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
| printing | moving blue wave + nozzle light | file running |
| paused | yellow breathing | any pause |
| filament | cyan/white chase | load/change/runout |
| alarm | red/white strobe | errors, cold pull |
| finished | green/white twinkle | print done |

Effects come from the klipper-led_effect extension (12 states above); the frame
chain is [neopixel printer_leds] 1-4, the nozzle light is LED 5. TOGGLE_LEDS
switches the FRAME off/on (sounds keep playing). After a finished print the
green/white celebration runs for `led_finish_time` seconds (default 10) and then
returns to idle breathing BY ITSELF — it used to twinkle forever.

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

## 18. Console messages

`[OK]` success · `[i]` info · `[!]` warning · `!!` error. M117 mirrors the
essence onto the LCD. Typical lines you will meet:

```
M104: 215C -> OVERWRITE -> 225C (layer 1)
M220 S100% capped to 65% (layer 1)
Layer 1: speed brake re-applied (65% after resume)
Layer 2: hotend -> 210.0C (override)
Sequential print: next object (NAME) - back to LAYER-1 temperatures
Temp tower: layer 21 -> 215C
Print running (legacy file) - live tuning and overrides ACTIVE
=== PRINT RUNNING === / Print finished: NAME (duration)
```

## 19. System: Klipper & Pi

| Command | Effect |
|---|---|
| SYS_FIRMWARE_RESTART CONFIRM=1 | Klipper restart (macros reload) — 2× |
| SYS_HOST_RESTART CONFIRM=1 | host service restart — 2× |
| SYS_SHUTDOWN CONFIRM=1 | heaters/fans/LEDs off → Pi shutdown via moonraker |
| SYS_SAVE_CONFIG | guarded SAVE_CONFIG: refuses during a print, skips when nothing is pending, warns that the LCD goes DARK for up to 2 min before restarting (2×) |
| HOST_CHECK | **Pi health report**: throttle/undervoltage flags (now + since boot), CPU temp, load **vs. core count**, **RAM + swap**, disk, **iowait**, **TOP CPU/RAM processes (top 5)** and **who sits IN the swap** (VmSwap per process — names the RAM eater even when the top-RAM list looks innocent) + **service states** (klipper/moonraker/avahi/crowsnest/sonar/OctoEverywhere/pigpiod, with warnings: double webcam stack, avahi still on, cloud relay) — honest verdict: THROTTLED / SWAPPING / OVERLOADED / OK. LCD: System > Host check |
| EMERGENCY_STOP | immediate halt |

All destructive paths need TWO presses (60 s window). Serial link: UART (ch. B.5).

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
| 11 gantry | Z motors wired in parallel on ONE driver — SYNC_GANTRY does the mechanical sync; watch the first run |
| 12 screws | screw positions live in [screws_tilt_adjust] in printer.cfg → ADJUST TO YOUR PRINTER |
| 15 objects | console users can always use Klipper's native EXCLUDE_OBJECT as well |

## 21. What happens when a macro executes

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
| **MCU 'Timer too close' shutdown** (host cannot feed the MCU) | ALWAYS a HOST problem — NEVER stepper current, never the electronics fan, never a safety trigger, and never a zip lying in the config folder (nothing scans it). **System > Host check** names it: THROTTLED = undervoltage (PSU/USB cable!) or heat · OVERLOADED = load >= core count, the Top-CPU list shows who — typical eaters on a Pi Zero 2: **webcam (crowsnest), sonar, OctoEverywhere, moonraker's object processing (enable_object_processing: True — your own moonraker.conf comment warns against it on a Pi Zero!)**, update manager, a fan/temp script with software PWM (RPi.GPIO) · SWAPPING = RAM full, SD-card swap stalls in bursts — **the verdict names the processes sitting in the swap („Top SWAP") directly** · also: after boot/update give the Pi ~2 min before starting a print (moonraker + watcher both re-scan the whole gcode folder while klippy parses the big config). Software side already hardened: mesh travels capped, preview pushes cost zero disk writes, meshes run adaptive |
| Mesh is full bed although 'adaptive' |: honest wording — 'full bed (file has no object data)' now SAYS so. The mesh before a held file runs adaptive (the watcher replays the file's EXCLUDE_OBJECT_DEFINE at selection); Orca files carry them when 'Label objects' is enabled. Plot/label/bridge files bring their own object polygon |
| KAMP meshes the whole bed | check KAMP_Settings.cfg margin — AND the file needs object data (see row above) |

Diagnostics: SHOW_STATUS · SELF_TEST · KAMP_STATUS · HOST_CHECK (Pi health) · _CHECK_INSTALL at boot.

## 23. Limits & known behavior

- sequential detection needs the previous object ≥1.6 mm tall (protects by-layer prints)
- legacy files (no APPLY_TYPE): feature factors apply instantly, but only the
  GLOBAL factor is re-applied at layer 2 / after resumes
- "State re-synced" after object-change resumes: cosmetic self-healing
- AS SLICED = no injections, but homing/mesh/prime still run BEFORE the file
- temperature tower holds the last temperature at the end — stop it afterwards
- a2d/accel_to_decel no longer exists — minimum_cruise_ratio replaced it everywhere

## 24. Cheat sheet: LCD paths & Mainsail commands

**LCD quick paths**

| I want to… | LCD path |
|---|---|
| print with my overwrites | Start Print? > AS LEGACY |
| print exactly as sliced | Start Print? > PRINT AS SLICED |
| system takeover of a sliced file | Start Print? > PRINT AS LEGACY |
| adjust Z live | Live Tuning > Z +0.04/−0.04 |
| hotend/bed/fan/Z-offset fast | Live Tuning > Hot / Bed / Fan / Zoff |
| slow everything down | Live Tuning > Speeds > Global |
| machine limits live | Live Tuning > Velocity |
| flow/PA/retraction live | Live Tuning > Extrusion |
| pause at layer 17 | Live Tuning > Pause & Control > Pause@: 17 |
| skip an object | Live Tuning > Objects (2×) |
| change material preset | Pre-Print > Material > LOAD NOW |
| compare with the file values | Pre-Print > Temps > File H:/File B: |
| first layer slower/faster | Pre-Print > 1st layer % |
| calibrate flow | Maintenance > Flow Cal. |
| run a temperature tower | Maintenance > Temp Tower |
| test ironing | Maintenance > Ironing Cal. |
| purge / cold pull | Macros > Purge · Maintenance > Filament |
| shutdown the Pi | System > Shutdown (2×) |

**Mainsail — the 20 you will actually use**

```
SHOW_STATUS · SET_MATERIAL MATERIAL=PLA · SET_OVERRIDE_VALUE NAME=… VALUE=… ·
TOGGLE_OVERRIDE NAME=… · CLEAR_OVERRIDES · PRINT_AS_SLICED / PRINT_WITH_OVERRIDES /
PRINT_AS_LEGACY · SET_GLOBAL_SPEED · SET_GLOBAL_ACCEL · SET_LIVE_VELOCITY ·
SET_LIVE_MINIMUM_CRUISE_RATIO · SET_LIVE_PRESSURE_ADVANCE · SET_LIVE_RETRACTION ·
SET_FLOW_RATE · SET_FAN_SCALE · PAUSE · RESUME · CANCEL_PRINT (2×) ·
PAUSE_AT_LAYER LAYER=n · SKIP_OBJECT OBJECT=name · CALIBRATE_PA ·
FLOW_CAL MEASURE=0.46 · TEMP_TOWER_START START=200 END=230 STEP=5 BAND=10
```

## 25. Complete macro index
All 127 public macros with parameters (defaults in parentheses; blank = no parameters). Internal helpers (leading `_`) are not user-facing. Grouped by module file — the same file you would edit.

### Sounds — 02_sounds.cfg (4)
| Macro | Parameters | Purpose |
|---|---|---|
| **M300** | P=100, S=1000 | single beep — wrapper; the real beep lives on as M99300 |
| **PLAY_SOUND** | NAME='r2_click' | play a tune by name (ch. 16) |
| **TOGGLE_SOUNDS** | — | sounds on/off (persisted: sound_on) |
| **TEST_SOUNDS** | — | play all 20 tunes in sequence |

### LEDs — 03_leds.cfg (5)
| Macro | Parameters | Purpose |
|---|---|---|
| **SET_LED_STATE** | STATE='idle' | switch the LED pattern (12 states, ch. 17) — applies the nozzle mode too |
| **NOZZLE_LED** | MODE, BRIGHT, R, G, B | nozzle light: on/off/auto + live dimming + live color (ch. 17) |
| **TOGGLE_LEDS** | — | frame LEDs off/on (persisted: leds_on) |
| **TEST_LEDS** | — | LED test animation |
| _NOZZLE_SET | ON | internal: writes LED 5 (color × brightness, capped 0.5) |

### Notifications — 04_notify.cfg (2)
| Macro | Parameters | Purpose |
|---|---|---|
| **NOTIFY** | TEXT, LEVEL='info', LED, SOUND | notification helper: text + sound + LED in one call |
| **SHOW_STATUS** | — | full status: mode, material, overrides, live values |

### Materials — 05_materials.cfg (3)
| Macro | Parameters | Purpose |
|---|---|---|
| **SET_MATERIAL** | MATERIAL=<current>, APPLY_PRESET=1 | select material; APPLY_PRESET=1 also loads its preset |
| **SAVE_MATERIAL_TEMPS** | MATERIAL=<current> | save current values as this material's preset |
| **SHOW_MATERIAL** | — | show the current material + its stored preset |

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

### Live tuning — 10_live_tuning.cfg (31)
| Macro | Parameters | Purpose |
|---|---|---|
| **APPLY_TYPE** | TYPE='' | feature switch: sets current_type + applies the active overrides for THIS feature (speed % x clean global via M99220, absolute accel via M99204, ironing flow via M99221) — injected after every ;TYPE: by the post-processor |
| **SET_OVERRIDE_VALUE** | NAME, VALUE | generic: NAME=feat_spd_<code> / feat_acc_<code> / feat_on_<code> for 12 codes + all legacy names; feat_on=0 resets speed→100% + accel→file M204 + ironing flow→slicer value |
| **SET_GLOBAL_SPEED** | PERCENT=100 | global speed % (M220 style, never capped) |
| **SET_GLOBAL_ACCEL** | ACCEL=4000 | global acceleration, mm/s² |
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
| **SET_OUTER_WALL_SPEED/ACCEL · SET_SUPPORT_SPEED/ACCEL · SET_IRONING_SPEED** | PERCENT= / ACCEL= | legacy-friendly per-feature setters: forward to feat_spd/feat_acc + ON — % sits on top of the CLEAN global |
| **SET_IRONING_FLOW** | PERCENT=100 | ironing-only flow override |
| **BABYSTEP_DOWN** | — | Z --0.04 mm live |
| **BABYSTEP_UP_FINE** | — | Z +0.12 mm — quick rescue step |
| **BABYSTEP_DOWN_FINE** | — | Z --0.12 mm — quick rescue step |

### Gantry — 11_gantry_sync.cfg (3)
| Macro | Parameters | Purpose |
|---|---|---|
| **SYNC_GANTRY** | FORCE=0, QUIET=0 | mechanical Z gantry sync (needs [force_move]) |
| **TOGGLE_GANTRY_SYNC_BOOT** | — | sync at every boot on/off |
| **TOGGLE_GANTRY_SYNC_PRINT** | — | sync at every print start on/off |

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
- console: `Macro system OK: all 16 modules loaded and current (build R2-2026-09-07.66)`
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
| .65 | postproc streaming: range generation + upload tagging no longer load whole files into RAM (32 MB source → Pi-safe memory), byte-identical outputs (golden test added) |
| .69 | file fixes IN PLACE (no re-upload): Pre-Print > File > RetFix file rewrites the selected file's retract pairs to G10/G11 on disk (markers survive), Vol->mm fix converts Marlin-volumetric E to mm (idempotent, beeps at start + done), start dialog auto-released; ~100 ms micro-pauses between multi-value disk writes (idle only) |
| .68 | file info shows the slicer + firmware flavor of every file (Orca/Prusa/Cura/Elegoo/Kiri:Moto/AstroPrint/SliceBeam … for Klipper/Marlin), loud warning on Marlin-volumetric files (Klipper counts E in mm), RetFix: old Bowden-era files re-uploaded with retracts rewritten to G10/G11 (current retraction applies, live-tunable) |
| .67 | print-start killer fixed (feature lists + material saves survive Klipper's command parser), generated files sort to the top (00_…_V version suffix, same name overwrites), label quality (glyph retracts, stroke ≤ cap/5, purge tower 15 mm on the probe-safe side), real fit preview on the LCD, labels up to 5 lines / near-bed size, filament stat in meters, SAVE+RESTART restarts when nothing is pending |
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
