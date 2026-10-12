# Making the LCD menus work on other displays

Analysis R132 (release .93). Question from the field: *the menus live on a
Creality 12864 (st7920) - how do other displays use them?*

**Verdict up front:** the menu tree (`menus/lcd_menues.cfg`) is plain Klipper
`[menu]` config with no hardware in it. It renders on **every display Klipper
supports** - the only per-machine work is the `[display]` pin block (and the
encoder/beeper pins), exactly like wiring up any stock Klipper LCD. Displays
that do not run Klipper's display stack (touch panels, vendor UIs) can never
show it - for those see the [Web UI](WEBUI_MOONRAKER.md).

---

## 1. What the menus actually require

| Requirement | Where | Portable? |
|---|---|---|
| Klipper `[display]` section with a supported `lcd_type` | `printer.cfg` | yes - one block per display |
| 4 text rows (reference: 16 columns) | menu design | yes on all 128x64 and 20x4/16x4 char LCDs |
| An encoder/click input (`encoder_pins`, `click_pin`) | `printer.cfg` | yes - every RepRap LCD has one |
| Short names (<= 16 chars, rule R29) | enforced by tests | already guaranteed |
| `menu_timeout` (optional, commented) | `printer.cfg` | cosmetic |

The tree itself uses only `[menu __main ...]` sections with `type: list /
command / input`, `name:` templates, `gcode:` bodies and `enable:` checks -
the core menu feature set that has been stable in Klipper for years. No custom
glyphs are used beyond the stock `>` marker.

## 2. Supported display classes (Klipper `lcd_type`)

| `lcd_type` | Typical hardware | Menus | Notes |
|---|---|---|---|
| `st7920` | Creality 12864, RepRapDiscount Full Graphic (the reference) | full | 128x64, 16 cols - exactly what the tree was designed for |
| `uc1701` | BTT Mini12864 ("Mini Display") | full | same 128x64 geometry; set `contrast` if pale |
| `emulated_st7920` | BTT TFT35 etc. wired in "12864 mode" | full | for panels that speak st7920 over SPI |
| `ssd1306` / `sh1106` | 128x64 I2C/SPI OLED | full | 16 cols x 8 rows of 8x8 glyphs; fine but small |
| `hd44780` / `hd44780_spi` / `aip31068_spi` | 20x4 / 16x4 character LCDs | full | character cells; the R29 name-length rule pays off here |

Per-display work in `printer.cfg` is only the `[display]` block:

```ini
[display]
lcd_type: uc1701            # <- the display chip
cs_pin: EXP1_4              # <- the wiring (board_pins aliases or raw pins)
a0_pin: EXP1_3
encoder_pins: ^EXP2_5, ^EXP2_3
click_pin: ^!EXP1_2
```

Wiring tables for the common boards are community-standard (SKR Mini E3,
SKR 2 / Pro, Creality 4.2.2 / 4.2.7 with `EXP1_1 = PC6` beeper etc.); the
Klipper `display.cfg` sample lists the EXP1/EXP2 pinouts for each.

## 3. What does NOT work - and the honest alternatives

| Display class | Why `[menu]` cannot reach it | Path forward |
|---|---|---|
| BTT / BIGTFT touch screens in touch mode | runs its own firmware UI; Klipper menus are not rendered | Mainsail/Fluidd macro panel now; Web UI (see `WEBUI_MOONRAKER.md`) for the exact tree |
| KlipperScreen on a Pi screen | own menu structure, does not consume `[menu]` sections | same as above; KlipperScreen lists the macros incl. `description:` |
| Printer-vendor screens (Bambu, stock firmware locked) | not Klipper-controlled at all | out of scope by definition |
| USB/serial "screen sticks" | no `[display]` driver in Klipper | out of scope |

Rule of thumb: **if Klipper's `printer.cfg` docs list the `lcd_type`, the menus
work; if the screen runs its own UI, they never will.**

## 4. Porting recipe (one display, 15 minutes)

1. Copy the matching `[display]` block from the Klipper display sample
   (pin aliases differ per mainboard - EXP1/EXP2 positions are printed on the
   boards).
2. Keep `menus/` unchanged: `printer.cfg` already includes
   `[include klipper-e3-r2d2/menus/lcd_menues.cfg]` inside/next to the
   `[display]`-carrying config; the tree activates as soon as `[display]`
   exists.
3. Wire the beeper the same way (`[pwm_cycle_time beeper]` + the pin) - or
   skip it and apply the guarded `M300` from
   [`PORTABILITY_SOUND_DISPLAY.md`](PORTABILITY_SOUND_DISPLAY.md).
4. Functional check on the new panel:
   * `__main` scrolls, every generator submenu opens (the 9 bricks catalog
     groups are the deepest tree),
   * an `input` item (e.g. *Bricks > Count*) steps and saves
     (`SAVE_VARIABLE` shows in the console),
   * the start dialog appears after selecting a generated file and both
     buttons fire their macros.
5. If the panel shows shifted output (uc1701 clones): adjust `contrast` /
   `x_offset` per the display docs - a wiring issue, never a menu issue.

## 5. Limits worth knowing before porting

* **Four rows, sixteen columns** is the design grid. 20x4 panels get two
  spare columns; nothing overflows (enforced by the R29 tests in
  `tools/macro_render_test.py`).
* **Menu timeout**: Klipper returns to the main screen after the (commented)
  `menu_timeout` - the state lives in `save_variables`, so re-entering a menu
  never loses the queue or settings.
* **No graphics**: the tree deliberately uses no icons/custom glyphs, so
  character LCDs lose nothing.
* **Encoder feel**: `menu_timeout` and click polarity (`^!`) differ per panel;
  both are one-line `printer.cfg` settings, nothing in the repo.

## 6. Summary

| You have ... | Do this | Effort |
|---|---|---|
| Any 128x64 RepRap-class LCD (st7920 / uc1701 / emulated) | `[display]` pin block for your board | 15 min |
| 128x64 OLED (ssd1306 / sh1106) | same + i2c/spi pins | 15 min |
| 20x4 character LCD (hd44780 family) | same | 15 min |
| Touch screen / KlipperScreen / vendor panel | Mainsail macro panel today, Web UI for the identical tree | see `WEBUI_MOONRAKER.md` |

## Sources

- Klipper Config Reference - display support and `lcd_type` options:
  https://www.klipper3d.org/Config_Reference.html#display-support
- Klipper display.cfg sample (EXP1/EXP2 pinouts per LCD type):
  https://github.com/Klipper3d/klipper/blob/master/config/display.cfg
- Community wiring examples (st7920 / uc1701 on SKR boards):
  https://klipper.discourse.group/t/st7920-display-settings-for-dual-extruder/1936
  and https://github-wiki-see.page/m/teeminus/NoTouchScreenFirmware/wiki/Klipper-display-configuration
