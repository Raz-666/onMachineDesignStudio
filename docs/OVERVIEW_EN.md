# R2-D2 / onMachineDesignStudio — System Overview

**Description baseline:** repository `main` as of 18 November 2026 (source build label: R2-2026-11-18.2). This document summarizes documented capabilities and architecture. It is not an independent safety certification or a guarantee that every feature works on every printer.

## In brief

R2-D2 is a substantial open control and creative toolkit for Klipper-based FDM printers. It combines G-code macros, LCD menus, Moonraker/Mainsail, a Python file watcher, print-file analysis, and many generators. Its core idea is to understand a print file’s layers, feature types, and parameters, then expose useful decisions and controls before and during a print.

The reference machine is a modified Ender-3 running Klipper, Moonraker, Mainsail, an SKR Mini E3 V3, and a 12864 LCD. According to `COMPATIBILITY.md`, Cartesian and CoreXY FDM printers are the target; Delta, belt, and resin machines are outside the documented scope.

## Architecture and data flow

```text
Orca/Cura/other G-code source
            │
            ├─ Optional slicer scripts: feature, layer, object markers
            ▼
G-code directory on Klipper host
            │
            ├─ systemd: tools/r2_postproc.py
            │     analyzes/annotates files, builds previews and generated files
            ├─ tools/r2_job_service.py
            │     job state, original archive, output validation
            ▼
Klipper macros and _STATE
            ├─ PRINT_START / PRINT_END, interceptors, layer/feature logic
            ├─ LCD menu: menus/lcd_menues.cfg
            └─ Moonraker/Web LCD: web/r2_menu.py + web/index.html
            ▼
Klipper host → MCU → printer hardware
```

`macros/01_state.cfg` separates persistent settings (`save_variables`) from volatile runtime state (`_STATE`). Macros make print-time decisions. More expensive G-code processing and generation are intended to run in the host-side watcher, not in Klipper Jinja templates on the reactor thread.

## Functionality

### Print preparation, materials, and file understanding

- A start dialog offers **AS SLICED** (run under the system’s intended file-preserving rules) or **AS LEGACY** (apply R2 overrides and preparation), plus cancellation.
- `PRINT_START` coordinates homing, optional gantry synchronization, bed/hotend heating, mesh decisions, and priming/purging.
- Many settings use a priority model: enabled user override, then file value, then material preset.
- Material profiles include PLA, PETG, ABS, ASA, and TPU, with editable/savable presets and optional per-file profiles.
- Layer-1/layer-2 temperature, fan, and speed rules are supported. Z-based layer tracking is a fallback when markers are absent.
- Older files that lack `PRINT_START`, `LAYER_MARK`, or feature markers can be detected/handled to a degree. Exact coverage depends on file content and print workflow.
- `_FILE_INFO` and file previews can show slicer/firmware hints, temperatures, layer height, material, feature inventory, and measured per-feature speeds and accelerations.

### Live tuning and feature recognition

- Global and feature-level speed, acceleration, flow, and pressure advance (PA); PA smoothing and live retraction where firmware retraction is configured.
- Fan controls include live value, scale, hold/clamp, and first-layer rules, with additional bridge-related behavior.
- Live temperatures, Z babystepping, motion limits, maximum velocity, minimum cruise ratio, and square-corner velocity.
- Feature categories include outer/inner wall, sparse/solid infill, top/bottom surface, bridge, internal bridge, gap, support, ironing, skirt, brim, prime tower, overhang, and custom. The project documents numbered C1–C9 slots for some unknown feature shapes.
- `APPLY_TYPE` changes settings at feature boundaries; `LAYER_MARK` marks layer boundaries. Slicer post-processors and the host watcher can supply those markers.
- The parser normalizes vocabularies from multiple slicers. The design intent is that unknown feature types remain visible as custom rather than silently inheriting the prior feature’s overrides.

### Pause, filament, and object controls

- Pause/resume, planned pause points, pause at layer N, planned normal stop at layer N, and two-step cancel confirmation.
- Filament load/unload, M600 changes, runout response, and purge-on-resume. Sensor features require compatible hardware configuration.
- Parking uses Z-lift, retraction, object/bed context, and a controlled resume sequence. Safety depends on correct bed, axis, probe, and printer configuration.
- Skip one object in a multi-object print when the file carries Klipper object definitions.
- Optional Z-hop on firmware retraction.

### Mesh, maintenance, and calibration

- Bed mesh ON/AUTO/OFF, profile management, and adaptive calibration via KAMP or native Klipper functionality where available and configured.
- Leveling, screw tilt, probe Z offset, extruder calibration, and hotend/bed PID tuning.
- Input-shaper measurement with a suitable accelerometer, plus documented manual shaper settings without measurement hardware.
- Calibration generators for temperature towers, PA/PA smoothing, flow, retraction, bridging, and ironing.
- Nozzle cleaning, filament care/cold pull, host/firmware restart, status reports, and self-tests.

### Generators and creative file processing

The project documentation describes LCD-accessible G-code generation or transformation for:

- **Layer ranges:** excerpts from an existing print, with optional floor/roof layers, brim, and centered holes.
- **Labels:** text plates with several stroke-font styles, hole/layout options, and optional color changes.
- **Plotter:** PNG/JPEG/SVG/vector-PDF/TXT to pen G-code, with draw/dot modes, scale, position, and pen offsets.
- **Lithophanes** and **ColorPic:** image-to-relief and stepped multi-color image output with corresponding print workflows.
- **Frames/display cases:** frames, backplates, stands, hanging options, and alternative closures.
- **Cable ties:** classic one-way and reusable LOOP variants.
- **Angle and flat connectors:** parameterized plates, holes, countersinks, and stiffeners.
- **Gaskets:** flat or profiled rings.
- **Bricks/kits/figures:** system-compatible building parts, kits derived from a G-code model, and assembled figures.
- **String Art:** image/spiral patterns made from an anchor frame and layered strands.
- **Texturing:** add deterministic fuzzy, patterned, or image-based texture to an existing file, especially outer walls.
- **File tools:** scale, cut/split layers, repair G-code, handle retraction or volumetric-E conventions, and create selected excerpts.

Generators create files, not certified components. Fit, strength, material, electrical/thermal loading, and suitability for safety-critical use require separate engineering and testing.

### Web UI, operations, and diagnostics

- `web/index.html` is a separate browser interface that mirrors the LCD menu and combines dashboard, G-code entry, status, notifications, and console.
- `web/r2_menu.py` provides Moonraker endpoints for menu/printer state and host information. Caching and pruning are intended to limit host load.
- `setup.sh` and `update.sh` support setup/update, checks, backups, and optional integrations. Updates still need to match the local printer configuration.
- `HOST_CHECK`, file/install checks, log and diagnostic packs, and emergency/triage tools support troubleshooting.
- Tests and audits include macro rendering, generator parameter sweeps, G-code invariants, regression checks, streaming, and installation. The CI workflow lists Jinja2 and Pillow as external test dependencies.

## What is distinctive

The differentiator is the combination of **printer control + file understanding + generation + multiple interfaces**:

1. A host watcher enriches files with layer, feature, and parameter information, rather than relying exclusively on slicer-side scripts.
2. The same file metadata is intended to drive file summaries, start decisions, layer behavior, and live feature overrides.
3. The LCD menu is intended as the central interaction model; the Web LCD mirrors it instead of maintaining an entirely separate menu tree.
4. Many generators are available directly from printer menus. This makes the printer a small local fabrication station, not only a G-code playback device.
5. User decisions (how a file should run) are combined with automation, file checks, and diagnostics.
6. The test/audit suite targets concrete Klipper, G-code, and host failure classes. `docs/SHUTDOWN_REGISTER.md`, for example, records historical timing/host-load incidents and mitigations.

This describes the project’s scope and design, not an industry-first claim. Most underlying building blocks—Klipper macros, post-processors, adaptive meshing, web dashboards, and generators—also exist separately in the wider Klipper and maker communities.

## Comparison with other solution types

| Approach | Typical emphasis | How R2-D2 differs |
|---|---|---|
| Manufacturer-integrated printer ecosystems | Easy setup, coordinated hardware/slicer/app workflows, vendor maintenance | R2-D2 provides more direct customization through macros and host scripts, at the cost of more user setup, validation, and maintenance. Exact differences depend on product model and firmware. |
| Typical Klipper community setup | Klipper + Moonraker/Mainsail or Fluidd, macros, and selected add-ons | R2-D2 bundles many concerns into a large configuration: start/live tuning, LCD, file watcher, Web LCD, generators, and diagnostics. A smaller community setup may be easier to understand and maintain. |
| OctoPrint-oriented setup | Host web UI and plugin/slicer integration; capability depends on printer firmware and plugins | R2-D2 is closely coupled to Klipper objects, Klipper Jinja macros, and Klipper motion controls. OctoPrint is not one firmware model; a fair comparison must specify the printer firmware and plugin set. |
| Scientific/industrial systems | Defined measurement methods, process control, documentation, validation, and sometimes certification | R2-D2 includes useful calibration, analysis, and audit tools, but the repository does not establish formal metrological traceability, industrial process qualification, or independent part certification. It is a community tool, not a validated laboratory or production system. |

## Performance: cost centers and constraints

The system is constrained by Klipper’s host reactor, MCU communication, memory, SD-card I/O, and available print time. Potential hot spots include:

- **Large Klipper menus and Jinja:** `menus/lcd_menues.cfg` is large and contains many dynamic entries. The tools inventory notes that Klipper renders dynamic menu text in its reactor; menu/status interaction can therefore contribute to workload.
- **Feature boundaries and command frequency:** `APPLY_TYPE`, layer markers, status messages, fan/PA/acceleration changes, and LED updates consume processing and/or communication. Frequent transitions or highly segmented G-code can magnify the cost.
- **File and geometry analysis:** G-code streaming is covered by tests, but geometric rasterization, image processing, STL export, large files, and broad audits consume CPU, RAM, and I/O.
- **Generator jobs:** lithophanes, ColorPic, String Art, and rasterized kits may take considerably longer on a Pi Zero 2 than small label or connector jobs. Queues, background work, RAM gates, and `nice` reduce risk but do not remove it.
- **Watcher and large file collections:** Large G-code directories, metadata/symlink management, rescans, and growing archives can increase I/O and processing time.
- **Live web requests:** The Web LCD polls printer status. Caches, object filtering, and quiet windows in the implementation reduce requests, but multiple clients, log retrieval, or poor timing can still add host workload.
- **LEDs during probing/homing:** LED updates share a communication path with motion on some hardware. The repository documents quieting LEDs during probe/homing phases and other mitigations for “Timer too close.”
- **Persistent writes:** Frequent writes of large state to the SD card can block the host or wear the card. The project moves rebuildable large lists to RAM and mirrors hot-path values in `_STATE`; persistent settings still involve I/O.
- **Practical guidance:** On a resource-constrained Pi, avoid generators and broad audits during time-sensitive print phases, configure optional services/object processing deliberately, and inspect host/Klipper logs during real prints.

## Compatibility and requirements

### Platform and integrations

- Klipper + Moonraker; Mainsail is the documented reference UI. The system uses Klipper Jinja macros, status objects, `save_variables`, delayed G-code, and renamed command interceptors.
- Cartesian and CoreXY FDM are in the documented scope. Delta and belt printers are not recommended because of rectangular-bed assumptions in placement and generation.
- KAMP is optional; native adaptive-mesh handling is the fallback where the necessary Klipper features and object information are available.
- OrcaSlicer and Cura guides are provided, and several other slicer vocabularies are documented. Exotic macros, firmware commands, or unknown feature semantics are not necessarily translatable.

### Hardware/configuration dependencies

- **Bed area:** For a non-reference printer, set the real usable area in the hardware configuration (`_R2_CONFIG`/`r2_hardware.cfg`). Axis limits and usable bed area are not necessarily the same.
- **Probe:** Probe offsets, reachable area, parking, and prime-line placement must match the hardware. Supervise the first print.
- **LEDs/sounds:** LED effects need `klipper-led_effect` and matching `[neopixel]`/`[dotstar]` configuration; sound needs a suitable buzzer. Optional hardware features may be unavailable or need disabling when hardware is absent.
- **Runout/filament:** A filament sensor and exact configuration section names are required. Without a sensor there is no automatic runout detection.
- **Live retraction:** Requires Klipper firmware retraction and compatible slicer/G-code settings. Without it, live control is limited.
- **Gantry sync:** `SYNC_GANTRY` targets the documented parallel-wired dual-Z arrangement; independent-Z machines should use the appropriate Klipper leveling method such as Z-Tilt/QGL.
- **Optional host/printer capabilities:** Input-shaper measurement needs an accelerometer; LCD/Web LCD and persistent LED setup may need optional components/extensions.
- **G-code interpretation:** Parsing and transformation depend on dialect and modal-state handling. Unusual/proprietary macros or unsupported movement modes can limit analysis or conversion.

## Limits and responsible use

- “AS SLICED” is a print mode; it does not necessarily mean the printer runs no startup sequence. `PRINT_START` may still perform homing, heating, meshing, and priming.
- Automatically inferred feature types are heuristics. The project marks derived data as such; geometry classification is not a full replacement for slicer semantics.
- Generated files are not validated structural, electrical, or certified safety components. Safety-critical use requires independent design and testing.
- Operation requires correct wiring, firmware configuration, mechanical limits, and supervision. Macros do not replace thermal fuses, smoke alarms, suitable power supplies, or electrical safety checks.
- The repository itself notes documentation drift risks; for example, it flags an open `MANUAL.md`/`MANUAL.pdf` divergence. Check current source and installation instructions before use.

## Conclusion

R2-D2 is an **integrated Klipper control, analysis, and generation system** for advanced makers. Its breadth comes from combining G-code understanding, layer/feature controls, LCD/Web interfaces, host-side processing, and printer-accessible generators. The tradeoff is significant complexity and dependence on correct hardware configuration, Klipper/Moonraker compatibility, and sufficient host performance.

### Repository references

- `README.md` — feature catalog and system concept
- `INSTALL.md` — installation, slicer, watcher, and integrations
- `COMPATIBILITY.md` — documented porting scope and hardware dependencies (note the older release status in that document)
- `DEVELOPMENT.md` — development and testing approach
- `docs/TOOLS_INVENTORY.md` — runtime, generators, tests, and diagnostics
- `docs/SHUTDOWN_REGISTER.md` — documented timing/host-load incidents and mitigations
- `macros/08_print_start_stop.cfg`, `macros/10_live_tuning.cfg`, `macros/01_state.cfg`
- `tools/r2_postproc.py`, `tools/r2_job_service.py`, `web/r2_menu.py`, `web/index.html`
- `slicer/ORCA.md`, `slicer/CURA.md`, `slicer/cura_KlipperFeatureTypes.py`
