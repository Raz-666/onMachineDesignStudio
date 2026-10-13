# UPDATE an existing installation (30 seconds, .50+)

You are already running the R2 system and got a new ZIP? This is ALL —
**upload the ZIP in Mainsail, then run ONE SSH command:**

1. **Upload the ZIP in Mainsail**: open the config files (the folder where
   your `printer.cfg` lives — you see the `klipper-e3-r2d2` folder there) and
   upload the ZIP **into that folder** (drag & drop or the upload button).
   NOT inside the `klipper-e3-r2d2` subfolder. (If Mainsail refuses the
   upload, your config folder is read-only in moonraker.conf — fallback:
   `scp klipper-e3-r2d2-*.zip pi@<pi-ip>:~/printer_data/config/`)
2. **SSH, one command** — unpacks over the old folder, checks, restarts:

```bash
bash ~/printer_data/config/klipper-e3-r2d2/update.sh
```

Coming from **.47 or earlier** (no update.sh on the Pi yet)? Same two steps,
just unpack once by hand:

```bash
cd ~/printer_data/config
unzip -o klipper-e3-r2d2-UPDATE-R2-2026-10-13.94.zip
bash klipper-e3-r2d2/update.sh
```

No `unzip` on the Pi?
`python3 -m zipfile -e klipper-e3-r2d2-UPDATE-R2-2026-10-13.94.zip .` does the
same — update.sh uses that fallback automatically.

**What update.sh does:** it finds the newest `klipper-e3-r2d2-UPDATE-R2-*.zip`
next to your printer.cfg, unzips it OVER the old `klipper-e3-r2d2` folder
(never touches variables.cfg or printer.cfg — all settings survive), then
verifies that this is the folder your printer.cfg includes, checks all 18
include lines, makes sure the .47/.48 `#` boot blocker is gone, sends
FIRMWARE_RESTART via Moonraker (also works while Klipper shows the red
config-error banner) and restarts r2-postproc (asks for sudo). An OLDER zip is
not unpacked unless you add `--force` (after a --force downgrade below .50 the
auto-unpack is gone with the old update.sh — unpack the newer ZIP once by hand
again). The uploaded ZIP can stay in the config folder (harmless) or be
deleted in Mainsail.

Boot sound + `M117 R2 ready` ~10 s later confirm success; the console line must
say `build R2-2026-10-13.94`

---

# The environment wizard: setup.sh (fresh installs AND after updates)

`update.sh` only swaps the package files. `setup.sh` (same folder) checks and
brings up **everything around the package** that the macro system needs to run
stable - for a fresh install and as a health check after updates:

- **Python** + watcher compile check (stdlib only - no pip dependencies)
- **r2-postproc service**: installed? running? pointing at THIS package? The
  unit file gets templated to your user + paths automatically (no `pi` needed)
- **KAMP**: detected; offered for installation (clone + config patches)
- **klipper-led_effect** (the LED effect library `03_leds.cfg` uses)
- **RAM + services**: top consumers, known-optional services (camera stack,
  OctoPrint, ModemManager, ...) - nothing is disabled without your OK
- **swap**: honest usage display + `vm.swappiness` tuning offer
- **hardware wizard (R108)**: every printer-specific value asked in English,
  each one validated + confirmed twice - build volume (bed min/max X/Y, Z
  height), probe offsets, nozzle-clean + part-presentation positions, LED
  layout (neopixel/dotstar, pin, chain, status/bed-light/nozzle areas, EBB
  CAN split chain). Result: **`r2_hardware.cfg`** - the SECOND variables file
  that survives deleting `variables.cfg` (your normal settings). Included
  from printer.cfg by one line the wizard adds for you.
- **LED wizard (R108)**: writes the `[neopixel]`/`[dotstar]` section (into
  r2_hardware.cfg - printer.cfg stays yours) and the effect index ranges;
  LCD: System > LED Setup tunes everything live afterwards
- **object processing** (moonraker): current state shown + explained, offered
  in BOTH directions - off is the deliberate recommendation on a Pi Zero 2 W
- **BACKUP FIRST + verified**: every file this run might change is copied and
  the copy verified byte-identical (cmp) BEFORE anything happens - a failed
  verify aborts the whole run
- **every change is shown first**: apply automatically (your lines only get
  commented out - NEVER deleted) / commented-only / separate txt file
  (safest - nothing is touched) / skip - your choice, asked once per run

```bash
bash ~/printer_data/config/klipper-e3-r2d2/setup.sh            # interactive
bash ~/printer_data/config/klipper-e3-r2d2/setup.sh --check    # report only
```

`update.sh` (R108) additionally asks whether to KEEP or CHANGE the current LED
+ hardware settings before it restarts anything (default: keep - the LED
layout is re-applied to the freshly unpacked 03_leds.cfg either way), shows
the object-processing state with an offer to change it, and runs the same
verified-backup-first routine. LCD persistence for the LED Setup menu needs
the `gcode_shell_command` extension (KIAUH installs it; setup.sh adds the
`[gcode_shell_command R2_PERSIST]` section into r2_hardware.cfg when it is
present - without it, LCD LED edits simply hold for the running session).

Every edited config file gets a `.r2bak.<timestamp>` backup first; questions
without input (non-interactive SSH) always take the safe default. Porting to
another printer: read `COMPATIBILITY.md` (what is dynamic, what to set once).

---

# Installation in ~10 minutes (ENGLISH rewrite)

## 0) Requirements (you already have these)

- Klipper + Moonraker + Mainsail on the Pi Zero 2 (path `~/printer_data/`)
- klipper-led_effect installed (KIAUH) - otherwise the [led_effect] sections fail
  (the system detects this and keeps running without LED effects)
- Creality 12864 LCD on EXP1/EXP2, beeper on PB5

## 1) IMPORTANT: migrate from the old German version

The rewrite renamed EVERYTHING (files, macros, variables, English only). Therefore:

1. **Delete the old macro folder on the Pi** (or replace it completely):
   ```bash
   rm -rf ~/printer_data/config/klipper-e3-r2d2
   ```
2. Upload this new `klipper-e3-r2d2` folder to `~/printer_data/config/`
3. **Delete the old stored variables** (key names changed):
   ```bash
   rm -f ~/printer_data/variables.cfg
   ```
   (It is recreated automatically 5s after the first start.)
4. Update the `[include]` lines in your printer.cfg (see step 3).

## 2) Adjust printer.cfg (your running config stays!)

Open `printer.cfg.example` as a **checklist** and compare with your printer.cfg:

1. **These sections must exist** (copy if missing):
   - `[save_variables]` filename: ~/printer_data/variables.cfg
   - `[exclude_object]`
   - `[display_status]`, `[respond]` (bare sections are enough)
   - `[firmware_retraction]`
   - `[filament_switch_sensor filament_sensor]` (your sensor: `switch_pin: !PC15`, `pause_on_runout: False`)
   - `[pwm_cycle_time beeper]` (pin PB5) - IMPORTANT: pwm_cycle_time, NOT output_pin
   - `[screws_tilt_adjust]` (ADJUST positions to your bed screw centers)
   - `[bed_mesh]` + `adaptive_margin: 5`
   - `[idle_timeout]` timeout: 3600
   - `[neopixel printer_leds]` (pin PA8, chain_count 5) - exact name! (the
     option is `chain_count` - the old `chain_cnt` spelling HALTS current
     Klipper; the setup LED wizard writes the section correctly for you,
     including dotstar chains and EBB CAN nozzle splits)
   - `[force_move]` with `enable_force_move: True` - REQUIRED for SYNC_GANTRY (registers `SET_KINEMATIC_POSITION`)
2. **Do not rename** these (macros use them): `filament_sensor` (sensor),
   `printer_leds` (neopixel), `beeper`, `_STATE`, `_MATERIALS`, `_SOUND_LIB`.
3. **MicroProbe**: `[probe]` with `pin: ^PC14`; adjust x/y/z_offset
   (PROBE_CALIBRATE via the Maintenance menu).

## 3) Includes at the end of your printer.cfg

```ini
[include klipper-e3-r2d2/macros/01_state.cfg]
[include klipper-e3-r2d2/macros/02_sounds.cfg]
[include klipper-e3-r2d2/macros/03_leds.cfg]
[include klipper-e3-r2d2/macros/04_notify.cfg]
[include klipper-e3-r2d2/macros/05_materials.cfg]
[include klipper-e3-r2d2/macros/06_temp_controls.cfg]
[include klipper-e3-r2d2/macros/07_start_confirm.cfg]
[include klipper-e3-r2d2/macros/08_print_start_stop.cfg]
[include klipper-e3-r2d2/macros/09_pause_filament.cfg]
[include klipper-e3-r2d2/macros/10_live_tuning.cfg]
[include klipper-e3-r2d2/macros/11_gantry_sync.cfg]
[include klipper-e3-r2d2/macros/12_maintenance.cfg]
[include klipper-e3-r2d2/macros/13_system.cfg]
[include klipper-e3-r2d2/macros/14_kamp.cfg]   <- NOT optional! see note below
[include klipper-e3-r2d2/macros/15_objects.cfg]
[include klipper-e3-r2d2/macros/16_labels.cfg]  <- NEW .47 (Labels menu + GEN_LABELS)
[include klipper-e3-r2d2/macros/17_generator.cfg]  <- NEW .70 (Kabelbinder + Winkel menus)
[include klipper-e3-r2d2/macros/18_colorpic.cfg]  <- NEW (R120: color pictures - Tools > ColorPic)
[include klipper-e3-r2d2/macros/19_bricks.cfg]  <- NEW (R121: building bricks - Tools > Bricks)
[include klipper-e3-r2d2/menus/lcd_menues.cfg]
```

(Paths relative to printer.cfg. Remove any OLD include lines pointing to the
deleted German files!)

**IMPORTANT - ALL 20 includes are required** (`16_labels.cfg` since .47, `17_generator.cfg` since .70, `18_colorpic.cfg` since R120, `19_bricks.cfg` since R121),
including `14_kamp.cfg` even
if you do NOT use KAMP: that file contains the mesh & purge dispatch
(`_CALIBRATE_MESH_PROFILE`, `_PURGE_SMART`) that EVERY print start calls - with
KAMP installed or with the native fallback. Skipping it breaks every print with
`Unknown command:"_CALIBRATE_MESH_PROFILE"`. After boot the console must say
`Macro system OK: all 17 modules loaded and current` - if not, run
`_CHECK_INSTALL`: every file carries a version sentinel, so MISSING and
OUTDATED copies (old file under the same name!) are reported by filename.

## 3b) Optional: install KAMP (Klipper-Adaptive-Meshing-Purging)

The system works without KAMP (uses Klipper's native `ADAPTIVE=1` + its own prime
line). With KAMP you additionally get the Voron logo purge and Smart Park.
`14_kamp.cfg` detects KAMP automatically - install order does not matter.

1. **Install KAMP** (official way, via SSH on the Pi):

   ```bash
   cd
   git clone https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging.git
   ln -s ~/Klipper-Adaptive-Meshing-Purging/Configuration ~/printer_data/config/KAMP
   cp ~/Klipper-Adaptive-Meshing-Purging/Configuration/KAMP_Settings.cfg ~/printer_data/config/KAMP_Settings.cfg
   ```

2. **Open `~/printer_data/config/KAMP_Settings.cfg`** and enable the includes you
   want (remove the comment marks):

   ```ini
   [include ./KAMP/Adaptive_Meshing.cfg]   # adaptive mesh (KAMP takes over BED_MESH_CALIBRATE)
   [include ./KAMP/Line_Purge.cfg]         # LINE_PURGE (our default purge with KAMP)
   # [include ./KAMP/Voron_Purge.cfg]      # alternatively: VORON_PURGE (logo)
   # [include ./KAMP/Smart_Park.cfg]       # SMART_PARK (optional, menu Maintenance > KAMP)
   ```

3. **In your `printer.cfg`** (in addition to our includes):

   ```ini
   [include KAMP_Settings.cfg]
   ```

4. **moonraker.conf** (object processing is mandatory, update manager optional):

   ```ini
   [file_manager]
   enable_object_processing: True

   [update_manager Klipper-Adaptive-Meshing-Purging]
   type: git_repo
   channel: dev
   path: ~/Klipper-Adaptive-Meshing-Purging
   origin: https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging.git
   managed_services: klipper
   primary_branch: main
   ```

   Then restart moonraker (`sudo service moonraker restart`).

5. `RESTART` -> LCD: **Maintenance > KAMP > KAMP status** must show "installed &
   loaded". Done - KAMP now does the adaptive mesh + purge automatically
   (toggleable in the same menu; our material mesh profiles are kept!).

## 3c) Pi shutdown from the LCD - works WITHOUT any extension

`SYS_SHUTDOWN` (LCD: System > 'Pi shutdown', press 2x) uses moonraker's remote
method `shutdown_machine` - the exact same call the Mainsail 'Shutdown' button
makes. Since you run Mainsail/moonraker, it works out of the box. No extension,
no sudoers entry needed.

> **IMPORTANT (your Pi is powered by the SKR mini!):** ALWAYS shut the Pi down
> via the LCD *before* switching the printer off - otherwise the SD card may
> corrupt. After the shutdown message wait ~10s, then cut power.

The old `gcode-shell-command` path is still supported as a fallback (if the
section exists, it is preferred) - but you do NOT need to install anything.

## 3d) Layer reader: the gcode post-processor (RECOMMENDED - since .40)

Klipper macros cannot read files - the ';LAYER_CHANGE' comments your slicer
writes never reach a macro. The post-processor closes that gap: it injects
`LAYER_MARK` + a `_FILE_INFO` block into EVERY gcode file that lands in
`~/printer_data/gcodes` (Mainsail upload, USB copy - no slicer script needed).
Result: exact layer events (fan + speed + L2 temps switch at the SAME instant,
no 8-second watcher delay) and the file's real parameters (line widths, flow
ratio, PA, layer count, by-object) in Pre-Print > File (G-code) - even for
foreign downloads.

One-time install on the Pi (SSH):
```bash
cp ~/printer_data/config/klipper-e3-r2d2/tools/r2-postproc.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now r2-postproc
systemctl status r2-postproc     # must say: active (running)
```

**Verify (2 minutes):**
```bash
systemctl status r2-postproc --no-pager -l   # must say: active (running)
journalctl -u r2-postproc --no-pager | tail -20
# how many files are still unprocessed? (0 = everything done)
grep -L 'R2-POSTPROC v4' ~/printer_data/gcodes/*.gcode 2>/dev/null | wc -l
```
The journal shows one `[ok] filename: +N LAYER_MARK ...` line per processed
file plus a summary after the start (`initial scan done: X files, Y processed,
Z already tagged`) and a heartbeat every 15 min (`still watching ...`). Since
.41 the service also fails LOUDLY when the gcodes path is wrong instead of
idling silently, and files with a 'future' modification time (Pi clock not yet
NTP-synced after boot) are processed instead of skipped forever.

Catch-up run by hand (processes everything once, then exits):
```bash
python3 ~/printer_data/config/klipper-e3-r2d2/tools/r2_postproc.py --watch ~/printer_data/gcodes --once
```
Files already sliced with the R2 script keep their own markers (only
_FILE_INFO is added). Without the service the system still works - the
Z-tracker counts layers as before (just less precisely, and without the file
parameters). After replacing the script: `systemctl restart r2-postproc`.

**Since .45 the same service does two more jobs** (no extra install step,
just restart it after the update):

- **Plotter conversions (.46: PNG, JPEG, SVG + vector PDF):** files named
  `name.png.gcode`, `foto.jpg.gcode`, `drawing.svg.gcode` or `plan.pdf.gcode`
  are converted IN PLACE into pen g-code (see MANUAL ch. 17) instead of being
  tagged. Auto-contrast (Otsu) makes the paper white, whatever its tint.
  Log lines: `[plot] foto.jpg.gcode: converted to pen-plotter g-code (2 pen(s), 953 lines)`.
- **Layer excerpts (.46: Z0.2 on the bed + floor/top/brim):** every 5 s it
  polls `range_nonce` in `~/printer_data/variables.cfg`; when Pre-Print >
  Range/Stop > Create changes the nonce, it builds `<name>_L<from>-<to>.gcode`
  (layer FROM as first layer at Z 0.2, optional floor/top/brim layers, a
  PRINT_START header with the source temps). Already up-to-date excerpts are
  skipped. Log line: `[range] file.gcode: layers 75-120 (51 layers, floor 3/top 2/brim 2)`.
- **File preview (.46):** when you select a file for printing, the watcher
  reads its parameters (layer height, nozzle, line width, temps, fan, PA) and
  pushes them to Klipper via **moonraker's local API** (127.0.0.1:7125) so
  Pre-Print > File shows them BEFORE the print starts. If moonraker is not
  reachable, this silently falls back to the old behavior (values appear when
  the print starts). Log line: `[preview] file.gcode: 17 values pushed to Klipper`.
  Test all three by hand:
  ```bash
  journalctl -u r2-postproc --no-pager | tail -5
  ```
- **Label generator (.47):** every 5 s it also polls `label_gen_nonce`; when
  Tools > Labels > Job > Create (or the console `GEN_LABELS TEXT="A|B" ...`) bumps it,
  it builds `Label_<text>_WxH.gcode` in the gcodes folder: solid bases with an
  optional golden-ratio hole, brim, ironing, a purge tower, `M600` filament
  change and the text on top - each label an exclude object. The file is
  tagged like any sliced file (normal Pre-Print flow). Bed limits come from
  your printer.cfg (stepper sections). Log line:
  `[labels] Label_WERKSTATT+1_60x30.gcode: 2 label(s), 2x1 grid (2 fit, using 2), 6 layers, tower on`
  - plus a beep and `Labels ready` on the LCD via moonraker.
- **Wichtig nach jedem Update (.46/.47):** `systemctl restart r2-postproc`
  (der Watcher liest die LCD-Plotter/Range-Werte jetzt korrekt - vor .46
  wurden die `variable_`-Namen in variables.cfg nicht erkannt und die
  Konvertierungen liefen immer mit Default-Werten!).

**Updates / upgrades:** each post-processor version has its own tag
(`; R2-POSTPROC v4` since .44). After an update, `systemctl restart
r2-postproc` re-processes everything found in the FIRST scan: files tagged v1,
v2 or v3 are UPGRADED in place (`[upgraded from v1/v2/v3]` in the journal) -
their LAYER_MARK lines stay, _FILE_INFO is replaced by the extended version
and ALL old APPLY_TYPE lines are rebuilt. v3 added Custom/Skirt/Brim as own
types and Gap infill as GAPS; v4 additionally MEASURES the real per-feature
speed (most frequent F value per ;TYPE segment) and accel (M204 in effect)
straight from the g-code and injects TYPES= (which features the file contains)
plus FS_*/FA_* originals - the LCD shows them and "override OFF" resets to
them. v4-tagged files are skipped as usual. The summary line after the
initial scan shows how many files were processed / upgraded / already tagged.

## 4) First start

1. `RESTART` -> check the console for errors -> `FIRMWARE_RESTART`
2. After ~10s: R2-D2 start sound + blue LED animation = everything alive.
3. Console: `SHOW_STATUS` -> should print all values.
4. LCD: the "Ender-3 R2D2" menu is there; try `Maintenance > Tests > Sound demo`.

## 5) Slicer setup

- **Orca**: `slicer/ORCA.md` step by step (start/end gcode, LAYER_MARK,
  label objects, firmware retraction, post-processing script on the slicing PC)
- **Cura**: `slicer/CURA.md` (start/end gcode + post-processing script in the
  configuration folder/scripts)

TIP: labeled objects also unlock the "Objects (Skip)" menu during prints
(LCD: Live Tuning > Objects) - single failed parts can be skipped right at
the display (`SKIP_OBJECT`, 2-press confirmation).

NOTE: the PRINT_START parameters were renamed to English in this rewrite
(`BED=`, `BED_AFTER=`, `HOTEND_FIRST=`, `HOTEND_AFTER=`, `LAYER_HEIGHT=`,
`OUTER_WALL_SPEED=`, `SUPPORT_SPEED=`, `IRONING_SPEED=`, `TOTAL_LAYERS=`) -
update your slicer start gcode accordingly (copy from ORCA.md/CURA.md).

## 6) First test print (recommended: small part, PLA)

1. Start the print -> it pauses and asks (LCD "Start Print?", R2 beeps, LEDs blink)
2. LCD: "Pre-Print > Material > PLA (load preset)" -> back to "Start Print?" ->
   "> PRINT W/ CHANGES"
3. Watch: homing -> bed heats (announced!) -> mesh (scanner LEDs!) -> hotend heats
   -> prime line beside the object -> happy sound -> printing (blue band + nozzle light)
4. During the print: LCD "Live Tuning" -> outer wall to 70% -> takes effect
   immediately (console shows every change)
5. Test: "Pause next layer" -> parks away from the object -> RESUME -> returns
   safely (first XY, then Z slowly)
6. Filament sensor test: pull the filament -> ALARM + pause -> M600 ->
   CHANGE_FILAMENT_RESUME

## 7) Good to know (how the system behaves)

- **PID tuning is MANUAL now** (Maintenance > PID Tuning): pick a temperature for
  hotend (with fan) or bed and it tunes + saves right away - anytime, not bound
  to materials, no automatic tuning in the print start anymore.
- **Old gcode files (no PRINT_START)**: the system pauses such a print right at the
  start, heats the bed, levels (material mesh profile) and purges - then continues
  automatically. Toggle: Pre-Print > Bed Mesh > 'Level old files'.
- **Layer-2 temperatures for old files**: files that lower the temperature for
  layer 2 (M104/M140 with a smaller value) get the 'after layer 1' override
  applied automatically. Files sliced with the PP script switch exactly at layer 2.
- **Per-feature speed/accel/ironing** needs the post-processing script
  (`slicer/ORCA.md` / `CURA.md`) - it writes TYPE markers into the gcode. Files
  WITHOUT markers (old files) can only be tuned GLOBALLY - the LCD shows
  'GLOBAL (old file)' in Live Tuning > Speeds as a reminder.
- **Bed mesh temperature**: meshing happens at print temperature (material preset
  or your manual value, Pre-Print > Bed Mesh > 'Mesh @ temp'). A cold bed is a
  different shape - that is why CALIBRATE_MESH heats first.

## 8) Troubleshooting

| Problem | Solution |
|---|---|
| `SAVE_VARIABLE` error on first start | wait 10s after boot (init runs 5s after start) - or run `_INIT_DEFAULTS` in the console once, then RESTART |
| LED effects missing | klipper-led_effect installed? (KIAUH) - everything else keeps working |
| Menu shows nothing new | correct `[display]` section? After RESTART re-open the menu (encoder click) |
| Live Tuning menu invisible during a print | should not happen anymore (state watcher) - run `SHOW_STATUS` and check "Mode:"; it must say `printing` |
| Adaptive mesh probes everything | slicer "label objects" on / Cura script active? Since .59 the watcher also REPLAYS the file's object definitions at selection - the mesh before a held file is adaptive even then. Plot/label/bridge files bring their own object polygon |
| `Unable to parse 'true' as a literal` | booleans must be Python style `True`/`False` (uppercase) in SAVE_VARIABLE / SET_GCODE_VARIABLE - never `true`/`false` |
| `Unknown command:"M300"` | M300 macro lives in 02_sounds.cfg and needs `[pwm_cycle_time beeper]` (not `[output_pin]`!) in printer.cfg |
| `G-Code macro rename of different types` | rename_existing for M/G-codes needs letter+digits names (e.g. `M99104`), nothing with underscores |
| `Can't register '...' as it is an invalid name` | macro names: UPPERCASE/digits/underscore only, no digit at position 1 or 2 (digits from position 3 on) |
| `Choice '...' for option '...' is not a valid choice` | value outside the allowed list, e.g. `screw_thread` only accepts `CW-M3`..`CCW-M6` (with direction prefix; Ender-3 bed screws: `CW-M4`) |
| `Unknown command:"_CALIBRATE_MESH_PROFILE"` (or other `_` macros) | the include for `14_kamp.cfg` is missing/commented in printer.cfg, or an outdated copy of the file is on the Pi - upload the complete current folder, add ALL include lines, `RESTART`. Then `_CHECK_INSTALL` must report all modules loaded |
| LCD menu shows entries that do not match the docs (e.g. no bed PID) | the `menus/lcd_menues.cfg` on the Pi is OUTDATED - upload the complete current folder. `_CHECK_INSTALL` now also verifies the menu file (sentinel `_V16_MENUS`) |
| `[force_move]` present but `// Unknown command:"SET_KINEMATIC_POSITION"` | the command is ONLY registered with `enable_force_move: True` in the `[force_move]` section (Klipper source behavior). Add it - otherwise the sync is a silent NO-OP. The current macro refuses loudly until then |
| `[force_move]` IS in printer.cfg but SYNC_GANTRY still refuses | that was a bug in the detection (force_move has no `get_status`, so the old check never saw it) - current version detects it via `configfile.settings`. Upload the current `11_gantry_sync.cfg` |
| `// Unknown command:"SET_KINEMATIC_POSITION"` | the `[force_move]` section is missing in printer.cfg - SYNC_GANTRY refuses to run (by design) until you add it. WARNING: older versions silently did NOTHING instead of bumping - if you synced without it, run SYNC_GANTRY again after adding |
| `!! Must home X and Y axes first` during gantry sync | fixed in the current version: Z probing needs X/Y positioned first ([safe_z_home]) - SYNC_GANTRY now runs a full G28 itself whenever any axis is unhomed |
| `Section 'gcode_shell_command poweroff' is not a valid config section` / printer halted | the extension is not installed but the section is in printer.cfg - simply comment the section out: SYS_SHUTDOWN now uses moonraker's `shutdown_machine` (no extension needed!) |
| `// Unknown command:"SHUTDOWN"` | ancient version - SYS_SHUTDOWN now shuts the Pi down via moonraker (`shutdown_machine`), no Klipper command needed |
| `!! Error on 'SET_IDLE_TIMEOUT TIMEOUT=0'` on every pause | fixed: Klipper requires timeout > 0 - pauses now use 31536000s (365 days = practically infinite) and restore the original value on resume |
| `!! Extrude below minimum temp` on pause of an old file | fixed: the anti-ooze retract now only runs with a hot hotend. (This error previously aborted the whole legacy-prep macro - the reason meshing 'never happened'!) |
| Mesh profile gone after a restart (`Unknown profile`) | by Klipper design a mesh is SESSION-only until `SAVE_CONFIG`. Now automatic: idle calibration saves immediately; a mesh measured during a print is persisted right after the print ends |
| Pause did not hold on old files | fixed chain: pause re-entry guard (no double-park), M24 only when really paused (no more 'SD busy'), legacy prep split into 2 phases with pause verification |
| `// Unknown command:"START_PRINT"` | old mod files call their old macro - there is now a no-op compatibility shim; the R2 system prepares the print anyway |
| `!! VARIABLE must not contain upper case` at boot | long fixed - all SAVE_VARIABLE names are lowercase; upload the current package completely and RESTART |
| Same error AGAIN after uploading the fix | an OLD copy of the file is still active on the Pi (wrong path or duplicate include). SSH check - this must return NOTHING: `grep -rn "VALUE=''" ~/printer_data/config/` - and compare your `[include ...]` paths against the actual folder |
| `Unable to parse '' as a literal` on RESUME / SKIP_OBJECT / SKIP_DISARM | fixed in the current version: Klipper parses parameters with `shlex` (shell mode) - quotes are stripped as shell quoting, so `VALUE=''` collapsed to an EMPTY argument. Empty strings must be written `VALUE='""'` (all 4 spots fixed). `tools/config_validator.py` now rejects this pattern |
| `Error evaluating 'gcode_macro PAUSE': ... no attribute 'timeout'` | fixed in the current version: PAUSE now reads Klipper's real status key `printer.idle_timeout.idle_timeout` (with fallbacks to the printer.cfg value and 3600s). Just upload the current `macros/09_pause_filament.cfg` + `08_print_start_stop.cfg` |
| Beeper quieter than expected | frequencies below 500/above 3000 Hz are hard to hear on these piezos (tunes already respect that) |
| `MCU shutdown: Timer too close` | the HOST fell behind feeding the MCU (never the printers fault - and never stepper current, the electronics fan or a safety trigger; a zip lying in the config folder is not scanned by anything either). Run **System > Host check** (`HOST_CHECK`): it decodes the throttle flags AND (.60) the load vs. core count, swap, iowait and the **TOP CPU/RAM processes** AND (.62) **who sits IN the swap** (VmSwap per process - names the RAM eater even when top-RAM looks innocent) + **the service states** (klipper/moonraker/avahi/crowsnest/sonar/OctoEverywhere/pigpiod, incl. warnings) - the honest verdict is THROTTLED / SWAPPING / OVERLOADED / OK. Typical Pi Zero 2 eaters: **webcam (crowsnest), sonar, OctoEverywhere, moonraker's object processing (`enable_object_processing: True` - your own moonraker.conf comment warns against it!), update manager auto-refresh, a fan/temp script with software PWM (RPi.GPIO - prefer pigpiod hardware PWM)** - switch off what you do not need. Also: after boot/update give the Pi ~2 minutes before starting a print (moonraker + watcher re-scan the whole gcode folder while klippy parses the config). .59 already removed avoidable load: mesh travels capped, preview pushes = zero disk writes, adaptive meshes. If THROTTLED: better PSU / shorter thicker USB cable - a throttled Pi cannot print reliably **.60 field diagnosis: SWAPPING (220MB swap!) + avahi-daemon at 99% CPU - swap only clears at REBOOT; disable avahi: `sudo systemctl disable --now avahi-daemon`, then reboot. .61 field diagnosis: STILL swapping (187MB) after only 25 min uptime with load 0.5 and Throttle NONE - avahi gone from the top, so something ELSE eats the RAM; the .62 Top-SWAP line + Services line name it - paste that report if unsure** |

## 9) Updates / your own changes

- Every macro file is **commented in detail** - every line explains what it does.
  Values like retract lengths, park corners, prime line positions are grouped and
  easy to change.
- After editing .cfg files: `RESTART`; after pin changes: `FIRMWARE_RESTART`.
- Own LED effects: add `[led_effect ...]` sections in 03_leds.cfg (colors <= 0.5!)
- Own sounds: add a tune string in 02_sounds.cfg ("freq:ms,...", 0:ms = pause)
- Validate your edits before uploading: `python3 tools/config_validator.py`
