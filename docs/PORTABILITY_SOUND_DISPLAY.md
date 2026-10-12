# Running the system without the beeper and without the LCD

Analysis R132 (release .93). Question from the field: *what happens on a Klipper
printer that has no beeper (or a different sound output) and/or not the Creality
12864 LCD the menus were built on?*

Companion documents:
[Web UI feasibility](WEBUI_MOONRAKER.md) - [LCD menu portability](LCD_MENU_PORTABILITY.md)
Base portability model (bed, probe, MCU, LEDs): see [COMPATIBILITY.md](../COMPATIBILITY.md)

---

## 1. Where sound and display are actually wired in

| Piece | File | Hardware dependency |
|---|---|---|
| `M300` (play tone) | `macros/02_sounds.cfg` | calls `SET_PIN PIN=beeper` |
| `[pwm_cycle_time beeper]` | `printer.cfg.example` | **the only hardware section** - one pin on the MCU |
| `_SOUND_LIB` (19 tunes) | `macros/02_sounds.cfg` | none - pure gcode loop |
| `PLAY_SOUND` / `TOGGLE_SOUNDS` / `sound_on` | `macros/02_sounds.cfg` | none |
| `[display]` (st7920 + pins) | `printer.cfg.example` | the LCD's SPI pins + encoder |
| `[menu ...]` tree (1643 menu entries) | `menus/lcd_menues.cfg` | none - pure config, inert without `[display]` |

Everything the user touches (generators, fixes, dialogs, live tuning) is a
**gcode macro with a `description:`**. The LCD is one possible front-end; the
Mainsail/Fluidd macro panel and the console are the other two. The macros never
read the display, and the display never writes state - UI actions only ever
call macros or `SAVE_VARIABLE`.

## 2. No beeper / a different sound output

### 2.1 What happens today if the pin is simply missing

`[pwm_cycle_time beeper]` is an optional hardware section. Without it:

* `_SOUND_LIB` still parses the tune and calls `M300 S.. P..`
* `M300` (the macro in 02_sounds.cfg) runs `SET_PIN PIN=beeper ...`
* **`SET_PIN` on a non-existent pin raises an error** - the tune dies on the
  first tone. Not fatal to the print (Klipper keeps printing), but every
  macro that plays a confirmation beep would print a console error, and the
  `G4 P..` pauses would still execute.

So "just delete the beeper section" is **not** clean. Two clean options:

### 2.2 Option A (recommended): keep the macro, guard the pin

Make the repo's `M300` macro hardware-agnostic - one Jinja check, no config
edits needed for silent printers:

```ini
[gcode_macro M300]
description: Play tone: M300 S<Hz> P<ms>
gcode:
    {% set S = params.S|default(1000)|int %}
    {% set P = params.P|default(100)|int %}
    {% if 'pwm_cycle_time beeper' in printer.configfile.settings %}
        SET_PIN PIN=beeper VALUE=0.5 CYCLE_TIME={ 1.0/S if S > 0 else 1 }
        G4 P{P}
        SET_PIN PIN=beeper VALUE=0
    {% endif %}
```

`printer.configfile.settings` reflects the *loaded* config, so the same
`macros/` tree works on printers with and without a buzzer - zero branching
in the 100+ call sites (`_SOUND_LIB NAME=...` stays as is).

### 2.3 Option B: different sound hardware

| Hardware | Config | Notes |
|---|---|---|
| Piezo on EXP1 (Creality 4.2.2/4.2.7 boards) | `[pwm_cycle_time beeper] pin: PC6` | only the pin changes - the common case |
| 5 V buzzer (non-piezo, "DC buzzer") | same section, it simply clicks instead of beeping | acceptable, or leave it off |
| `[output_pin beeper] pwm: True` (classic Klipper sample) | works too - `SET_PIN ... CYCLE_TIME` is supported by pwm output pins | alternative pin type, same macro |
| I2S / RGB speaker boards (Bambu-class, KlipperScreen boxes) | **no M300 equivalent** | use Option A (silent) + LEDs + Web-UI sounds |

### 2.4 What carries the feedback when the printer is silent

The system was designed for degraded-sound operation already (R95, rule cc:
feedback beeps stay silent *during* prints on every printer - oozing guard):

1. **NeoPixel effects** - `SET_LED_STATE` runs on every state change
   (idle / heating / printing / paused / error / dialog). `[neopixel]` is
   optional in the same way; without it `SET_LED_STATE` degrades to a no-op
   with one console notice.
2. **`M117` status line** - shown in Mainsail/Fluidd header and on any LCD.
3. **`RESPOND MSG=...`** - 565 call sites across the macros; every decision a
   dialog offers on the LCD is also announced in the console.
4. **Browser sounds (future)** - the Web-UI analysis (`WEBUI_MOONRAKER.md`)
   covers mirroring the `_SOUND_LIB` tune table with WebAudio, so the *phone*
   beeps even when the printer cannot.

### 2.5 Verdict

Sound is a **one-section, one-macro swap**. With the Option-A guard (a 3-line
change, planned for the next round) the system runs 100 % clean on silent
printers: no errors, no config surgery, `TOGGLE_SOUNDS` still works, and the
`sound_on` state is simply ignored by a muted `M300`.

## 3. No LCD at all

### 3.1 What actually stops working

Nothing structural. `[menu]` sections are ignored by Klipper when no
`[display]` section exists - they cost nothing. The complete feature set is
reachable through:

* **Mainsail / Fluidd macro panel** - every macro carries a `description:`
  with its parameters ("GEN_FIGURES SCALE=100 COUNT=2 MODE=PARTS ..."), which
  the panels display as documentation. This is the zero-work fallback.
* **Console** - same macros, typed.
* **The Web-UI concept** - same tree, better ergonomics (see
  `WEBUI_MOONRAKER.md`).

### 3.2 The one real gap: guided flows

The LCD shines at *guided* flows - the start dialog (print as legacy / sliced?
retract fix first?), the pre-print fix chain, the bricks queue. Without any
display these still work (they are macros: `PRINT_AS_LEGACY`, `AS_SLICED`,
`FIX_FILE WHAT=RETRACT` ...), but the user has to read `RESPOND` output in
Mainsail instead of being walked through. Mitigation:

* `M117` shows the pending decision on the Mainsail status chip,
* `07_start_confirm.cfg` announces both options with their exact macro names,
* the planned Web-UI renders the same dialogs as buttons - that is precisely
  the "LCD-feel without LCD" deliverable.

### 3.3 Recommended kit for a headless printer

1. Mainsail or Fluidd (already required for Moonraker anyway),
2. `docs/WEBUI_MOONRAKER.md` web UI for the menu tree,
3. the M300 guard from 2.2 if there is no buzzer.

## 4. Summary matrix

| Target system | Beeps | LCD menus | Effort |
|---|---|---|---|
| Same-class printer + 12864 LCD + piezo | yes | yes | pin mapping only (see `LCD_MENU_PORTABILITY.md`) |
| Printer with different display chip (uc1701, SSD1306, hd44780) | yes | yes | same doc, different `lcd_type` block |
| Printer with touch screen (BTT TFT, KlipperScreen) | yes (if beeper pin) | **no** (`[menu]` does not render) | Mainsail panel now / Web-UI later |
| Headless (Mainsail only, no beeper) | no | no | M300 guard + macro panel; Web-UI recommended |
| Headless + browser sounds | in the browser | Web-UI | `WEBUI_MOONRAKER.md` |

## Sources

- Klipper Config Reference, display support (lcd_type list):
  https://www.klipper3d.org/Config_Reference.html#display-support
- Klipper sample beeper implementation (`[output_pin]` + M300 macro):
  https://dev.to/wallclocks/enable-buzzer-in-klipper-for-creality-boards-422-427-19mg
- Moonraker installation (nginx is the static-file server, Moonraker is API-only):
  https://moonraker.readthedocs.io/en/latest/installation/
