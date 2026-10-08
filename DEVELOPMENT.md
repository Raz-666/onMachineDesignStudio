# Development digest

The short, public version of this project's engineering journal. The full
journal — 105 rounds, every field log, in German — stays private; this page
tells you what matters.

## How this system is built

**Field-log driven.** Every feature and every fix starts as a real observation
from the actual printer (console logs, HOST_CHECK reports, print results) —
not from a spec. Each round: reproduce, root-cause, fix, and pin the behavior
down with tests before it ships. That is why the release notes read like a
diagnosis log — they are one.

**Nothing ships without the net.** Five check batteries gate every release:

| Battery | What it proves | Size |
|---|---|---|
| Macro render suite | every Klipper template renders correctly (full printer-object simulation, incl. KAMP present/absent, unhomed axes, paused prints, ...) | 1247 tests |
| Golden byte-identity | generator output is byte-identical to frozen references (regression net) | 23 cases |
| Audit sweep | emitted g-code obeys the invariants (bed bounds, z-monotonic, retract balance, ;TYPE: honesty) | 59 files |
| Streaming simulations | the watcher's RSS stays flat while huge files stream (no 'Timer too close' ammo) | all pass |
| Megatest | every generator at parameter extremes, idempotency, expect-error cases | 101 runs |

All five run on every push and pull request (see `.github/workflows/tests.yml`)
— and in any fresh clone: `python3 tools/macro_render_test.py` is the entry
point, the only external dependency is `jinja2`.

## Milestone digest

- **Layer markers + file info watcher** — a systemd-watched post-processor tags
  every g-code that lands in the folder (uploads, USB, scp) with layer markers,
  `;TYPE:` feature activation and a `_FILE_INFO` block; the LCD/menus and the
  start sequence act on it.
- **Generators on the printer itself** — picture frames & display cases
  (presets, RECT/OVAL, backplate, glue kit, stand), labels (5 stroke fonts,
  GROW/FIXED), cable ties, angle plates, bridging tests, gaskets, lithophanes,
  layer-range excerpts, input-shaper resonance plates. All placed safely inside
  the real bed — the axis range is deliberately lifted on the reference
  machine, so placement never trusts it.
- **Pen-plotter mode** — PNG/JPEG/SVG/PDF/TXT → pen g-code with LCD-settable
  bed, offsets, scaling, stipple/draw modes.
- **KAMP integration** — auto-detected; adaptive mesh/purge dispatch with
  honest fallbacks (native `ADAPTIVE=1`, own probe-safe prime line).
- **Host health tooling** — HOST_CHECK (throttle, load vs. cores, swap
  *activity* — quietly parked pages are OK, real swap traffic is not), the
  environment wizard `setup.sh` (watcher service templating, KAMP/led_effect
  install, optional-service asks, swap tuning).
- **Hardening history worth reading** — the megatest round found a plot-scaling
  bug (small images exploded off the bed); a field log exposed a false
  'SWAPPING!' alarm; and the portability audit found the honest way to carry
  machine-specific values: a KAMP-style `[gcode_macro _R2_CONFIG]` settings
  macro (a raw custom section makes Klipper refuse to boot — we know, we
  halted a real printer finding that out).

## Conventions

- `update.sh` swaps the package over an existing install (ZIP in the config
  folder, one command), `setup.sh` brings the *environment* up (fresh installs
  and health checks after updates).
- English in the shipped files, German in the private journal.
- Defaults are the reference machine (Ender-3 class); everything
  machine-specific lives in `[gcode_macro _R2_CONFIG]` (see
  COMPATIBILITY.md).
