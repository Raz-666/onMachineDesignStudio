# Cura setup (for the Ender-3 R2D2 macro system)

Cura passes fewer parameters to start gcode than Orca - that is fine: whatever is
missing comes from the material preset or the pre-print dialog.

## 1) Machine start gcode (Settings -> Printer -> Manage printers ->
##    Machine settings -> Start G-code)

```gcode
PRINT_START MATERIAL={material_type} BED={material_bed_temperature_layer_0} BED_AFTER={material_bed_temperature} HOTEND_FIRST={material_print_temperature_layer_0} HOTEND_AFTER={material_print_temperature} LAYER_HEIGHT={layer_height} OUTER_WALL_SPEED={speed_wall_0} SUPPORT_SPEED={speed_support} IRONING_SPEED={ironing_speed} TOTAL_LAYERS={layer_count}
```

> If your Cura version does not know a placeholder (older versions): simply remove
> that part (e.g. `OUTER_WALL_SPEED=...`) - missing values fall back to the preset.

## 2) End G-code

```gcode
PRINT_END
```

## 3) Post-processing script (provides LAYER_MARK + APPLY_TYPE + object box)

Cura has no "layer change gcode" field - the script adds all three:

1. Cura: **Help -> Show configuration folder** (open it)
2. Copy into its **`scripts`** folder (create it if missing):
   `scripts/KlipperFeatureTypes.py`  (from this folder, keep that exact name!)
3. **Restart Cura**
4. **Extensions -> Post processing -> Modify G-code -> Add a script ->
   "Klipper: Feature-Types & Object-Box"**

> The script generates:
> - `LAYER_MARK` at every `;LAYER:` (layer counter, 1st/following temps, layer pause)
> - `APPLY_TYPE TYPE=...` at every `;TYPE:` (speed/accel/flow per feature, live)
> - `EXCLUDE_OBJECT_DEFINE` with the total bounding box (adaptive mesh,
>   collision-free parking; Orca does this per object, Cura gets the total box)

## 4) "Pause at height" (Cura extension)

Cura's **Pause at height** script sends `M0` - our system intercepts M0 and parks
collision-free. It works together with the LCD menu 1:1.

## 5) Recommendations in Cura

- **Retraction**: Cura keeps its own retract values by default. For LIVE retract
  tuning on the LCD enable Experimental -> "Firmware retraction" and set Cura's
  retract values to 0 (values come from this system per material). Without it:
  retract is only changeable BEFORE the print (Pre-Print menu), not live.
- **Temperatures**: Cura writes temps into the profile - our overrides (Pre-Print
  menu / live setters) reliably replace them anyway, even mid-file.

> Bonus: with the script active the LCD gains the "Objects (Skip)" menu during
> prints (Live Tuning > Objects) - skip a failed part directly at the display.
