## What this is

`Raz-666/onMachineDesignStudio` is a large, field-tested Klipper control system for a modified Ender‑3. It combines printer macros, LCD menus, Moonraker/Mainsail integration, slicer post-processing, G-code generators, and a web-based LCD mirror.

The repository targets a Raspberry Pi Zero 2 W / Klipper host and prioritizes real-time MCU safety, print recovery, maintenance automation, and on-machine artwork generation.

### Stack
- **Languages:** Python 88.1%, HTML 9.7%, Shell 2.2%
- **Runtime:** Klipper, Moonraker, Jinja-templated G-code macros, systemd
- **Notable libraries/tools:** Jinja2, Klipper led_effect, KAMP, Moonraker APIs
- **License:** GNU GPL-3.0-or-later

## Potential performance issues

- **Klipper serial-bus flooding.** Feature changes, LED effects, status messages, and repeated `SET_GCODE_VARIABLE` calls can generate substantial MCU traffic. The code contains explicit serial-budget and `Timer too close` protections, but very frequent `APPLY_TYPE`, `M106`, M204, or PA changes remain potential hotspots.
- **Large Jinja macro rendering.** Files such as `macros/10_live_tuning.cfg` perform complex conditional rendering and repeatedly query printer state. This can make macros expensive to evaluate, particularly on slower Pis or during homing and print-start windows.
- **Full G-code and STL processing.** The Python tools and generators can perform geometric calculations, image decoding, STL validation, and whole-file rewrites. Large lithophanes, textures, and long G-code files may consume substantial CPU and memory.
- **Web-status polling.** `web/r2_menu.py` still polls printer state from Moonraker and caches results for only 2.5 seconds. Polling too aggressively or asking for unpruned objects could stall Klippy's reactor.
- **Watcher and poll loop concurrency.** The G-code post-processor polls multiple nonce channels and watches for uploads. Concurrent jobs, duplicate watchers, or unbounded threads could cause CPU contention or repeated file processing.
- **Full log and file reads.** Log exports now cap their reads, but broad G-code analysis or crash-log exports can still read and retain several megabytes at once on a memory-constrained Pi.
- **Repeated `SAVE_VARIABLE` operations.** Several macros historically triggered excessive saved-variable updates. Although the code now mirrors state into `_STATE`, persistent writes can still be slow if used in hot paths.
- **Generated output volume.** Labels, bricks, frames, plotter output, and range excerpts create and validate many G-code/STL files. Repeated initial directory scans or unbounded archives can grow disk usage and processing time.
- **Monolithic web payload.** `web/index.html` is nearly 888 KB and `menu_structure.json` exceeds 1 MB. Combined with generated menu data, browsers may experience slow initial parsing or memory usage.
- **LCD menu complexity.** `menus/lcd_menues.cfg` is roughly 769 KB. Rendering many menu entries or live Jinja fragments can make display navigation or input handling feel slow.
- **Configuration initialization.** `setup.sh` and `update.sh` perform package verification, backups, service setup, optional software installation, and configuration rewrites. Running them with several unrelated optional services enabled can make setup slow.

## How it's organized

```text
macros/          Klipper state, print control, tuning, maintenance, LEDs
menus/           12864 LCD menu definition
slicer/          Orca/Cura post-processing integration
tools/           G-code post-processing, generators, audits, test harnesses
web/             Moonraker endpoints and browser-based LCD interface
analyse/         Architecture, review, field evidence, and audit records
testfixtures/    Large representative G-code stress fixtures
docs/            Generated or supporting documentation
backups/         Backup-related repository content
```

**How it fits together:** `printer.cfg` includes the `macros/*.cfg` modules and `lcd_menues.cfg`. Slicer scripts inject feature and layer markers into G-code; `tools/r2_postproc.py` performs a broader host-side post-processing pass; `r2_job_service.py` manages and validates generated outputs; and `web/r2_menu.py` exposes a pruned view of the printer state to the browser UI.

## How to run it

For the interactive environment setup:

```bash
bash ~/printer_data/config/klipper-e3-r2d2/setup.sh
```

For a report-only setup check:

```bash
bash ~/printer_data/config/klipper-e3-r2d2/setup.sh --check
```

Validate macros locally:

```bash
python3 tools/config_validator.py
python3 tools/macro_render_test.py
```

Run the post-processing watcher manually:

```bash
python3 ~/printer_data/config/klipper-e3-r2d2/tools/r2_postproc.py \
  --watch ~/printer_data/gcodes --once
```

The normal installation relies on Klipper, Moonraker, Mainsail, a configured `printer.cfg`, and a working filesystem layout under `~/printer_data`.


## Low-level overview

This repository is primarily a **Klipper macro system**, with a Python host-side service layer for G-code processing and generation.

### Runtime architecture

- `printer.cfg.example` supplies hardware sections and include ordering.
- `macros/01_state.cfg` stores volatile and persistent state.
- `macros/02_sounds.cfg` through `19_bricks.cfg` implement the print state machine, LCD actions, live tuning, maintenance, LEDs, and generators.
- `menus/lcd_menues.cfg` exposes macros as a 12864 LCD hierarchy.
- `tools/r2_postproc.py` runs on the Pi as a systemd watcher.
- `tools/r2_job_service.py` manages background generation and validates outputs.
- `web/r2_menu.py` exposes Moonraker JSON endpoints for the web LCD.
- Slicer scripts add `LAYER_MARK`, `_FILE_INFO`, and `APPLY_TYPE` metadata.

The main runtime flow is:

```text
Slicer output
  -> optional slicer postprocessor
  -> gcode directory
  -> r2_postproc watcher
  -> metadata/tagging/generation
  -> Moonraker/virtual SD card
  -> Klipper macros
  -> MCU motion and hardware
```

### Major Python components

- `r2_postproc.py`: G-code parsing, tagging, range extraction, generators, STL export, host checks, and image/PDF decoding.
- `r2_job_service.py`: thread-safe job lifecycle, original-file archiving, SHA-256 verification, and output validation.
- `r2_job_service.py` and generator code: atomic writes using temporary files and `fsync`.
- `r2_menu.py`: Moonraker component with menu export, live printer state, CPU/RAM, and klippy-log endpoints.
- `macro_render_test.py` and many `test_*.py` files: Jinja or mocked-printer validation.

### Major macro components

- State/variable initialization
- Temperature and fan interceptors
- Print-start and print-end choreography
- Pause, resume, cancel, filament runout, and M600 handling
- Per-feature speed, flow, acceleration, PA, and retract tuning
- Gantry synchronization
- Mesh, probe, PID, and input-shaper maintenance
- KAMP/native meshing dispatch
- Object exclusion and skipping
- Poweroff and host restart

## Potential performance issues

- **Macro execution can block Klippy.** Files like `10_live_tuning.cfg` and print-state macros execute Jinja loops and repeatedly query printer objects. Functions should avoid long macros in hot paths such as homing, feature boundaries, and every layer.
- **State synchronization writes.** `SAVE_VARIABLE` operations can trigger disk writes and Klippy config reload effects. The code reduces this with `_STATE` mirrors, but repeated `_SYNC_*` calls or file modifications could still create I/O bursts.
- **Frequent feature changes.** `APPLY_TYPE` sends M220/M221, acceleration updates, PA, fan, and Jinja expressions per feature boundary. Large files with frequent alternating feature comments can produce many serial commands.
- **LED and sound traffic.** LED animations and `M300` events may add many MCU operations. The repository documents MCU flooding as a historical issue.
- **Post-processing is CPU-heavy.** `_litho_grid`, JPEG/PNG decoding, geometry rasterization, and G-code streams can consume an entire Pi core. Image decoders materialize many RGB/luma structures despite step subsampling.
- **G-code range and STL analysis are highly expensive.** Range extraction, feature audits, `audit_tag_geometry`, and STL export perform full-stream parsing and grid/raster operations. `r2_postproc.py` contains several long loops and retains several per-file structures.
- **One-job queue only partially isolates CPU.** `_JOB_YIELD` pauses every few iterations, but image decode and STL writing can perform long internal operations without yielding.
- **High-resolution raster masks.** `_layer_ink_mask` grows grids, stamps every segment, and performs flood-fill and contour tracing. It has a six-million-cell safety cap, but repeated generators can still allocate several MB-to-tens-of-MB buffers.
- **Embedded font dictionaries.** `r2_postproc.py` embeds very large font maps, increasing Python startup memory and import time.
- **Web live polling.** The Moonraker endpoint caches only 2.5 seconds, while the browser and several tabs can still generate overlapping requests. Configfile and save-variable snapshots are especially expensive.
- **Recursive scans.** Directory scans for G-codes, generator outputs, symlinks, log tails, and STL exports can become O(number of files × number of passes), especially with large gcodes folders.
- **Memory for original archives.** `OriginalArchive` hashes and copies G-code streams in chunks, but repeated archive manifests and validation histories can grow indefinitely.
- **Filesystem operations.** Atomic writes use temporary files plus `fsync`/`os.replace`; frequent rewrites or large G-code files can cause disk and SD-card latency.
- **Test suite cost.** Macro-render, megatest, geometry, stress, and golden-byte suites execute a very large matrix. Running all tests on CI or the Pi may be slow.

## Potential compatibility issues

- **Klipper version drift.** It depends on macros and objects such as `firmware_retraction`, `input_shaper`, `printer.toolhead`, `save_variables`, and Moonraker APIs. Renamed or removed fields may break Jinja evaluation.
- **Strict Jinja syntax.** Klipper Jinja supports a limited subset. Inline comments, `{{ }}`, Python-only filters, Python booleans, and unsupported formatting can halt Klippy or break macros.
- **Moonraker API differences.** `r2_menu.py` supports only some server method fallbacks. Older Moonraker versions may lack `/server/files/notify_filelist_changed`, `lookup_component`, or status fields.
- **Python version differences.** The code assumes modern Python features and pathlib behavior but does not declare an explicit minimum Python version. Older Raspberry Pi OS releases may lack compatible standard-library APIs or dependencies.
- **JPEG support is partial.** Progressive JPEG files are explicitly rejected; only baseline JPEG and selected PNG color types are supported.
- **PDF support is limited.** The PDF parser extracts basic paths from Flate-compressed streams and ignores text/fonts. Nonstandard PDF encodings or compressed streams may fail.
- **SVG support is incomplete.** It supports a subset of SVG shapes, paths, transforms, and Béziers but not CSS, definitions, groups, masks, clips, or full SVG path grammar.
- **Binary STL assumptions.** STL validation assumes little-endian binary STL and exact 84-byte header layout. Text STL and malformed STL variants are not fully supported.
- **G-code modal-state correctness.** Custom modal parsing is not complete. Multi-axis G0/G1, G2/G3, absolute/relative E, tool changes, coordinate offsets, and slicer-specific comments can diverge from actual motion.
- **Slicer dialect coverage.** Recognition is broad but heuristic. Unknown `;TYPE:` names fall to CUSTOM or approximate mappings, and Kiri/Simplify3D/FlashPrint/Bambu variants may use different comments.
- **Path and filesystem assumptions.** The code assumes Linux paths, `/proc`, systemd, Moonraker’s `~/printer_data` layout, GNU tools, and a writable SD card. Windows, macOS, or containers may fail.
- **Symlink security and portability.** `os.link`, `O_NOFOLLOW`, `dir_fd`, and symlink assumptions are Linux-specific and may fail on filesystems or containers.
- **G-code output must be 3D-printer-safe.** The geometry generators use bed-limit heuristics and Slicers' printer profiles. Incorrect config values or larger toolhead geometry can place generated objects outside printable or probed areas.
- **Hardware profile assumptions.** Some macros assume Creality 12864, BTT SKR Mini E3, MicroProbe, Ender‑3 dimensions, and a specific NeoPixel layout. Compatibility is not automatic.
- **KAMP availability.** Adaptive mesh and purge behavior differs with or without KAMP, object processing enabled, or Moonraker support.
- **Filament and retract assumptions.** Firmware retraction requires `[firmware_retraction]`; Bowden/direct profiles differ, and live retraction is unsupported or partial without Klipper macros.
- **Klipper MCU timing.** Repeated LED updates, G10/G11, live shaper changes, and status pushes may interact badly with old MCU firmware or slower hosts.
- **Power and shutdown safety.** Pi shutdown depends on Moonraker and correct relay wiring. [USB/CAN] and optional BTT electronics sections contain hardware-specific, commented examples that can be unsafe if modified incorrectly.
- **Python standard-library-only claim.** The host tools avoid pip dependencies, but optional features expect Pillow-like external support or system utilities such as `unzip`, `systemctl`, `ps`, `vmstat`, and `vcgencmd`.

## Low-level hotspots to inspect first

- `tools/r2_postproc.py`: `audit_tag_geometry`, `make_range`, `make_labels`, image decoders, `_copy_picked_image`
- `tools/r2_job_service.py`: `OriginalArchive`, `_validate_binary_stl`, `_validate_text_gcode`
- `web/r2_menu.py`: `_handle_live`, `_prune_status`, `_pi_measure`
- `macros/10_live_tuning.cfg`: `APPLY_TYPE`, `_SET_PA`, `_SYNC_OV_FEAT`
- `setup.sh` / `update.sh`: systemd and system configuration changes
- `macros/14_kamp.cfg` and `08_print_start_stop.cfg`: print-start and mesh timing
- `printer.cfg.example`: hardware pins and required config sections