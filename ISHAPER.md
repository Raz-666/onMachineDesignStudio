# Input Shaper / Resonance Calibration — the full manual

This guide walks you through vibration calibration ("input shaping") for your
Ender-3 from installing an accelerometer to the final saved values — via LCD
(`Maintenance > Vibration Cal.`) **or** Mainsail (`CALIBRATE_SHAPER`).

---

## 1. What is input shaping and why calibrate it?

Every printer frame rings like a bell when the print head accelerates: belts,
the gantry and the bed spring back and forth a few times per direction change.
On the print this shows as **ringing / ghosting / echoes** — visible ripples on
straight walls next to corners or text, and it limits how fast you can
accelerate at all.

Klipper's *input shaper* slightly "pre-distorts" the acceleration commands so
the spring-back of one impulse cancels the next one. To do that well it needs
to know your printer's **resonance frequencies** — and those must be measured,
not guessed. That is what the accelerometer calibration does:

- moves the head through a frequency sweep per axis,
- records the vibrations with the accelerometer,
- computes the best shaper type + frequency for X and Y,
- reports how much smoothing each option would add and which max acceleration
  it can support.

Typical result on a stock-ish Ender-3: **40–60 Hz** on X, **30–50 Hz** on Y.

## 2. Hardware: what you need

An accelerometer supported by Klipper. Common and cheap:

| Chip | Boards | Notes |
|---|---|---|
| ADXL345 | BTT ADXL345 module, many "Klipper kits" | the classic, 3.3 V SPI |
| LIS2DW / LIS3DH | BTT "Smart Accelerometer", some boards | newer, lower noise |
| MPU-6000/9250 | generic GY modules | works, mount quality matters most |

**Two ways to wire it:**

1. **To the printer board (SKR mini E3)** — SPI pins of your board (see its
   pinout document: SPI section, plus any free CS pin). Keep the wires SHORT
   (< 10–15 cm) and twisted; long loose wires ruin the measurement.
2. **To the Pi (recommended by Klipper docs)** — the same ADXL345 module on the
   Pi's SPI pins. Enable SPI with `sudo raspi-config` (Interface Options > SPI),
   then Klipper reads it directly from the host. No load on the print MCU.

In both cases the module must be mounted **rigidly** to the moving part you
want to measure:

- **X axis (and general "both")**: fixed to the print head / hotend — tight,
  directly screwed or double-sided-taped to a stiff part, cable strain-relieved.
- **Y axis**: fixed to the BED for a stock Ender-3 (the bed is the Y mover!).
  A head-mounted sensor measures Y through the belt — bed mounting is more
  accurate. Calibrate, then move the sensor between the two positions.

> Orientation does not need to be perfect, but keep the axes roughly aligned
> (module X pointing to printer X). Loose tape, dangling cables or a sensor
> flopping around produce garbage data — if the results look wildly different
> between runs, remount it.

## 3. printer.cfg setup

Two sections (see `printer.cfg.example` for placement):

```ini
# accelerometer on the Pi host:
[adxl345]
# (on the SKR mini E3 instead: spi_bus/spi_software_sclk_pin etc. of YOUR
#  board's SPI pins + a free CS pin as cs_pin: - check the board pinout!)

[resonance_tester]
accel_chip: adxl345        # must match the section name above
probe_points:
    117.5, 117.5, 20       # EXAMPLE Ender-3: bed center, 20mm above the bed
    # one point is enough; more points = longer test, averaged picture
```

After adding: `RESTART`, then verify the wiring:

- LCD: `Maintenance > Vibration Cal. > Dump raw data` (or `DUMP_RESONANCES`)
- the head does two short test moves and Klipper writes
  `~/printer_data/compressor/r2-*.csv` on the Pi.

If that works, the wiring is good. You can also open those CSV files in
Mainsail (Calibration & Shaping) to see your raw vibration picture.

## 4. Calibration — step by step

1. **Preparation** (matters more than the test itself):
   - belts at correct tension (a ruined belt tension cannot be tuned away),
   - wheels/rails snugged, no loose bolts, print head cable not dragging,
   - bed glass/plate mounted as when printing, EMPTY bed is fine.
2. **LCD:** `Maintenance > Vibration Cal.` — you will see:

   | Entry | Meaning |
   |---|---|
   | `X <shaper> <freq>` | current values (click = console status line) |
   | `Calibrate X` / `Calibrate Y` / `Calibrate X + Y` | run the test |
   | `Freq from: 0Hz` | lower bound of the sweep (0 = Klipper default 5 Hz) |
   | `Freq to: 0Hz` | upper bound (0 = Klipper default 120–133 Hz) |
   | `Max smooth: 0.00` | smoothing cap, 0 = unlimited (see below) |
   | `Auto save: ON` | SAVE_CONFIG automatically after the test (one restart) |
   | `Dump raw data` | write the CSVs for graphing |

3. Run **Calibrate X + Y**. The system homes if needed, turns heaters and fans
   off, then sweeps each axis (1–2 min per axis — the head buzzes in rising
   pitches, that is normal). Watch the console: Klipper prints a table per axis
   with every candidate shaper, its frequency, the **smoothing** it adds and
   the **recommended max acceleration**.
4. Klipper automatically applies the best candidate per axis and (with
   `Auto save: ON`) saves + restarts once. The status line then shows e.g.
   `X mzv 47.3 | Y ei 38.9`.

Mainsail: `CALIBRATE_SHAPER AXIS=BOTH`, with options if you want:
`CALIBRATE_SHAPER AXIS=X FREQ_START=5 FREQ_END=120 MAX_SMOOTHING=0.2 AUTOSAVE=1`.

## 5. Reading the results like a pro (community practice)

Klipper's choice optimizes smoothing vs. ringing — a good default. If you want
to fine-tune (Ellis' tuning guide method):

- **Smoothing** rounds corners: too much shaper = fuzzy details. If the auto
  choice picks a very low-frequency shaper with high smoothing, set
  `Max smooth: 0.20` and re-run — Klipper then picks the best option UNDER
  that smoothing budget.
- **Frequency support**: higher shaper frequency generally allows higher
  acceleration. `Calibrate X + Y` twice (once free, once with the smoothing
  cap) and compare — pick the compromise you like.
- **Verify with a test print**: print a ringing tower (Orca's calibration menu
  has "Vibration - Ringing" tests per axis). If ghosting is gone on both
  axes, you are done.
- **Set your max acceleration**: the console report suggests a value — put it
  into `[printer] max_accel` in printer.cfg (this is NOT written
  automatically). The R2 system's per-feature accelerations stay relative on
  top of it.

## 6. When to recalibrate

- after belt replacement/tension change, new wheels/rails, frame bolts,
- after changing the hotend mass (new fan duct, heavy nozzle setup),
- after moving the sensor or the cable routing,
- when you see new ghosting at higher speeds.

The values are stored in printer.cfg via SAVE_CONFIG — recalibrating simply
overwrites them.

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `No [resonance_tester] in printer.cfg` | sections missing or Klipper not restarted after adding them |
| `adxl345` errors / no data | wiring (SPI pins, CS), SPI not enabled on the Pi, chip name must match the section (`lis2dw`, `mpu6000`, ...) |
| Results differ wildly between runs | sensor not rigid, cable dragging, belts loose — remount and re-tension first |
| Frequencies below ~20 Hz or above ~120 Hz | suspicious: check belt tension (too slack = very low Y freq) and mounting |
| `Must home axis first` | should not happen (the macro homes) — check that homing itself works |
| Smoothing warning in the console | Klipper suggests a lower smoothing — set `Max smooth` and re-run |

## 8. Command reference

| Command | Parameters | Effect |
|---|---|---|
| `CALIBRATE_SHAPER` | `AXIS=X\|Y\|BOTH` `[FREQ_START]` `[FREQ_END]` `[MAX_SMOOTHING]` `[AUTOSAVE=1]` | home, heaters/fans off, SHAPER_CALIBRATE per axis, report, optional SAVE_CONFIG |
| `DUMP_RESONANCES` | `[AXIS=X\|Y\|BOTH]` | write raw CSVs (`r2-*.csv`) for the graphs |
| `RESONANCE_DIAGRAM` | `[AXIS='BOTH']` `[MODE='PRINT'/'PLOT']` | .48: CSVs → printed/plotted diagram (PSD + 5 shaper curves + shaper table, winner boxed) |
| `SHAPER_RESULT` | `[AXIS]` `[TYPE]` `[FREQ]` | .48: show the table / apply the picked shaper (freq from the table) live + boot override |

Everything the LCD does is a normal macro — Mainsail can drive it all.


## 9. The printed diagram + shaper pick (.48)

`CALIBRATE_SHAPER` prints its recommendation into the console — nice on a
screen, gone later. **Vibration Cal. > Diagram (print)** makes the watcher
build `Resonance_XY.gcode` from your CSVs (newest per axis; `save_path` from
`[resonance_tester]`, fallback `/tmp`): one plate per axis with the PSD curve
(log scale like Klipper's graph), all 5 shaper response curves, the peak
marker with its Hz and the **shaper table** (nr / shaper / freq / remaining
vibrations % / smoothing) — the recommendation boxed + "OK". **Diagram
(plot)** draws the same with a pen (`Resonance_XY_plot.gcode`). The print
goes through the normal start flow (mesh + purge line + temperatures,
babystepping works), single color, ~1.5 mm thin.

Read the paper, then **Vibration Cal. > Apply result > X/Y > shaper** — the
stored frequency of that shaper applies via `SET_INPUT_SHAPER` (live) and is
saved as the **boot override** (`ishaper_ov_*`): it survives every restart,
your printer.cfg stays untouched. Console equivalents:
`SHAPER_RESULT` (table), `SHAPER_RESULT AXIS=X TYPE=MZV`,
`SHAPER_RESULT AXIS=Y TYPE=EI FREQ=58` (manual fine tuning).

If the CSV comes from plain `TEST_RESONANCES`/`DUMP_RESONANCES` (no shaper
table inside), the watcher fits the shapers itself — a faithful port of
Klipper's `shaper_calibrate` math (ZV/MZV/EI/2HUMP_EI/3HUMP, test damping
ratios 0.075/0.1/0.15, same scoring and selection), so the table matches
what Klipper would recommend for the same data.
