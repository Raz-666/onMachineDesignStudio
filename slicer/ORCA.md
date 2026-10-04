# OrcaSlicer setup (for the Ender-3 R2D2 macro system)

Everything under **Prepare -> Printer -> Printer settings -> Custom (machine gcode)**
- plus two checkboxes elsewhere. Copy & done.

## 1) Start G-code (machine start gcode)

Use this block as your ENTIRE start gcode (it replaces ALL heating commands -
PRINT_START heats by itself and announces every step):

```gcode
PRINT_START MATERIAL={filament_type[0]} BED={first_layer_bed_temperature[0]} BED_AFTER={bed_temperature[0]} HOTEND_FIRST={first_layer_temperature[0]} HOTEND_AFTER={temperature[0]} LAYER_HEIGHT={layer_height} OUTER_WALL_SPEED={outer_wall_speed} SUPPORT_SPEED={support_speed} IRONING_SPEED={ironing_speed} TOTAL_LAYERS={total_layer_count}
```

> Meaning: PRINT_START knows the file's values and can compare/replace them with
> your overrides. `HOTEND_AFTER` is the temperature from layer 2 on - exactly this
> "steady" temperature is also used for the PID decision.

## 2) End G-code (machine end gcode)

```gcode
PRINT_END
```

## 3) Layer change gcode

**Prepare -> Process -> Other settings -> G-code -> "Layer change G-code":**

```gcode
LAYER_MARK
```

> Klipper counts layers (first-layer vs. following temps!), shows the layer on the
> LCD and can "pause at layer N" / "pause next layer".

## 4) Label objects (for adaptive mesh + collision-free parking)

**Prepare -> Process -> Other settings -> Options: enable "Label objects".**

> Orca then writes EXCLUDE_OBJECT_DEFINE into the file. Needed for: adaptive bed
> mesh (probe object area only), the prime line BESIDE the print, and the
> collision-free park corner choice on pause/filament change.

## 5) Firmware retraction (so retract is live-tunable on the LCD)

**Prepare -> Process -> Other settings (Advanced?): enable "Use firmware retraction".**

> Orca stops writing its own retract values (uses G10/G11 instead). Values are set
> per material by this system (05_materials.cfg) and changeable DURING the print
> (menu Live Tuning -> Extrusion).

## 6) Post-processing script (speed/accel PER FEATURE live-tunable)

Copy this folder anywhere onto your SLICING PC (not the Pi!) and register it in Orca
under **Prepare -> Post-processing scripts**:

```
python3 /path/to/klipper-e3-r2d2/slicer/orca_klipper_features.py;
```

- Windows: `python "C:\klipper-e3-r2d2\slicer\orca_klipper_features.py";`
- **Do not forget the semicolon** (Orca's separator for multiple scripts)

> The script inserts an `APPLY_TYPE` command after every `;TYPE:Outer wall` change.
> Only then can Klipper control outer wall/support/ironing separately. Without the
> script: global M220/M221 tuning + all other features still work (and the live
> setters apply immediately).

## 7) Filament change in Orca (optional, multi-color prints)

Process -> "G-code on filament change" can stay empty or contain `M600` - our M600
macro parks collision-free, unloads, waits and purges on resume.

## 8) What you NO LONGER need

- No `M190/M109` in start gcode (PRINT_START does it with announcements)
- No purge/skirt in start gcode (adaptive prime line is done by the system)
- No `SET_PRESSURE_ADVANCE`/`M900` in start gcode (set per material by the system)
- KAMP purge/adaptive-mesh not required: Klipper can do ADAPTIVE natively
  (BED_MESH_CALIBRATE ADAPTIVE=1) - used automatically, KAMP optional.

> Bonus: with labeled objects the LCD gains the "Objects (Skip)" menu during
> prints (Live Tuning > Objects) - skip a failed part directly at the display.
