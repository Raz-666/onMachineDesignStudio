# Tools inventory — what is what, and what proves it

**Shutdown register:** `docs/SHUTDOWN_REGISTER.md` — every crash site,
its cause, its fix and the test that holds it, in one table.

*Stand: R2-2026-11-18.3 (V4). Auto-checked against reality by
`tools/r165_doc_check.py`; the version line here is not typed by hand —
see "The version rule" below.*

This page answers the question the MANUAL deliberately does not: **the
MANUAL describes what the printer does, this describes the machinery that
makes it do it.** Six groups; the tables below carry the per-file line
counts (`wc -l` at the release). Everything in group A ships to the Pi
and runs during a print; everything in group E never leaves the
repository.

---

## A. On the printer — the core runtime (ships)

| File | Lines | What it does |
|---|---|---|
| `tools/r2_postproc.py` | 30 322 | **The engine.** One systemd service, four jobs: (1) the *layer reader* — tags every new g-code with `LAYER_MARK`/`APPLY_TYPE` markers, a `;TYPE:` map and a `_FILE_INFO` block, so the LCD, the menus and the live tuning know what is printing before layer 1; (2) **every generator** (range, labels, plotter, cable ties, angles, lithos, gaskets, frames, bricks, kits, figures, colorpic, string art, geometry, scale/taper/twist, mirror, STL export, cake cut) — the LCD only sets variables, the real work happens here, off the print thread; (3) the *watcher* — folder watching, preview pushes, queue handling, the recovery tick; (4) **HOST_CHECK** (throttle, load vs cores, swap *activity*, hidepid honesty) and the MCU auto-recovery. Streaming, one line in / one line out — no full-file buffers (a full buffer is what kills the Pi's RAM and then the print). |
| `tools/r2_postproc_next.py` | 30 322 | **The experimental copy.** Byte for byte `r2_postproc.py` at the moment of R252, plus its own header. From now on new post-processor work happens HERE and the stable file is not touched. Never started directly: the service starts the stable file, which reads the pp_engine switch (LCD System > PP engine, variables file) and hands over via runpy when it says `next`; a syntax error or a crashed handover keeps the stable engine and brakes the switch for 15 min. |
| `tools/toolchain.py` | 873 | **The chain engine (R259).** `plan_chain()` turns a preset file (JSON, `presets/toolchain/` + the gcodes `Toolchain/` folder) into a validated step plan - tool registry, parameter schema, file-name globbing, honest refusals (unknown tool, missing file, empty plan = `[]`). `run_chain()` executes it streaming: per-step temp workspace (`§22.4` - a step's temp is deleted the moment the next step adopts it), optional `validator`, `output_mode='save'`, `cancel_check`, the `on_output` gate (every artifact passes through it before it becomes the next step's input) and `on_step` progress (R261: fires at step START, cosmetic - a broken hook can never kill a chain). |
| `tools/toolchain_steps.py` | 184 | **The real adapters.** Each supported tool as one `Step` (command, param mapping, produces/consumes). The registry is the single place that decides what is chainable - and what is not (the cake cutter refuses: it is a hand-over cut, not a file-to-file transform). |
| `tools/r2_collect.py` | 384 | **The evidence pack ('Doctor').** Builds ONE support file: build stamps, host (RAM/swap/disk/load/top/throttled/dmesg), the three services + journals, the watcher state files, variables.cfg, printer.cfg, a compact incident digest out of klippy.log (events, the worst Reactor stalls WITH stacks, MCU statistics around each shutdown), the last 3 MB of the raw log, the newest MCU snapshot, the gcodes inventory. Writes gcodes/crash_archive/R2-DOCTOR-<stamp>.txt + a .txt.gcode twin (Mainsail only lists printable files) - the post-processor skips every R2-DOCTOR-* name. Idle-gated, read-only, no sudo. Started by the LCD (System > Diagnostics), by the watcher (doctor_nonce) or by hand. |
| `tools/r2_texture.py` | 1 409 | **The texture engine** (called by r2_postproc, also standalone): FUZZY (Orca-style fuzzy skin), BUMPS (27 seamless patterns) and MAP (a picture wrapped around the part). Rewrites only the outer wall of an existing file — `;TYPE:`, E/Z/F and EXCLUDE_OBJECT stay byte-identical. |
| `tools/r2_cake.py` | 543 | **The cake-cut engine**: splits a print with a plane, E redistributed per section. |
| `tools/r2_persist.sh` | 161 | Persists a variable into `variables.cfg` from a shell context (the LCD writes, the printer keeps it across a reboot). |
| `tools/r2-postproc.service` | 21 | The systemd unit — restart always, one watcher only. |
| `web/r2_menu.py` | 732 | The Moonraker extension behind the web UI (`/server/r2_menu/live`, `/sd`, `/pistats`, …). Caches, so several browser tabs cost one request. |
| `web/index.html` | 1 863 | The single-page web UI (live values, menu mirror, file browser, SD list). Polls 3 s, holds a 25 s quiet window after any start command. |
| `web/menu_structure.json` | — | Generated from `menus/lcd_menues.cfg` by `tools/menu_json_export.py` — the menu tree the web UI renders, so a macro change reaches the browser without a second implementation. |
| `web/install_web.sh` | — | Installs the extension next to Moonraker. |

**Rule of thumb:** if a feature can be explained as "the LCD sets a
variable, the engine builds the file", it belongs in this group. The .cfg
files must never do heavy work themselves — Jinja runs on the print
thread's reactor.

---

## B. Install & update

| File | Lines | What it does |
|---|---|---|
| `setup.sh` | 794 | Brings the *environment* up: venv-less dependency checks, watcher service templating, KAMP/led_effect install, optional-service asks, swap tuning, web extension. Fresh installs and post-update health checks. |
| `update.sh` | 617 | Swaps the package over an existing install (`unzip -o` + restart), keeps `variables.cfg`, kills stray watchers (`[r]2_postproc.py` — the bracket keeps pkill from matching itself), optional `--git` path. |
| `tools/r2_setup_lib.sh` | 937 | Shared shell library: distro detection, service templating, safe config edits. |
| `tools/r233_update_check.sh` | 481 | Update-integration check (pins the update path itself). |
| `tools/repair_git.sh` | 34 | Repairs a broken `.git` in a field install. |

---

## C. Documentation builders

| File | Produces |
|---|---|
| `tools/make_manual_pdf.py` | `MANUAL.pdf` (107 pages) — the illustrated handbook. |
| `tools/make_texture_pdf.py` | `TEXTURING.pdf` (30 pages) — the full pattern catalog, every pattern sampled from the real pattern functions, plus the preset mapping. |
| `tools/make_feature_pdf.py` | `FEATURE_TAGGING.pdf` (14 pages) — the `;TYPE:`/layer-marker system in depth. |
| `tools/make_displays_pdf.py` | `DISPLAYS_WEB_UI.pdf` (11 pages) — behaviour with other displays / Mainsail / web UI. |
| `tools/make_cakesplit_pdf.py` | `CUTSPLIT.pdf` (7 pages) — the cut & split methodology. |
| `tools/make_generators_pdf.py` | `GENERATORS_TOOLS.pdf` (13 pages, R2-2026-11-18.3) — all eleven generators plus all fifteen file tools (R263: + Toolchain), one block each: where in the menu, what comes out, **the real LCD rows read out of `menus/lcd_menues.cfg`** (so the page cannot drift), honest limits, one tip. |
| `tools/make_creative_pdf.py` | `CREATIVE_POSSIBILITIES.pdf` (11 pages, R2-2026-11-18.3) — **On-Machine Design Studio for Creative Freedom**: thirteen recipes (R263: + Effektkette/Toolchain) that COMBINE the tools (texture × light, MAP relief, litho+frame+stand, labelled texture, brick structure, string art, scale/twist/mirror variations, cutting, colour, workshop parts, STL round trip, safety tools), plus Modellbau/Deko-Sets/Doppel-Durchgänge chapters, a Fehlersuche-und-Optimierung chapter (symptom → cause → tool), wall-thickness/light tables, what the system deliberately does not do — closing with the commissioned line: „kein PC, kein 3D-Programm, keine KI — nur ein Drehrad.“ |
| `tools/r2_version.py` | **Not a builder — the version rule.** |
| `tools/make_label_fonts.py` | Build-time helper for the embedded label fonts. Never needed on the Pi. |

### The version rule

`tools/r2_version.py` reads the release string from `macros/01_state.cfg`
(the same string the LCD shows and `r199_zip_check.py` verifies) and every
builder stamps its pages from it:

```python
from r2_version import VERSION as _R2VER     # 'R2-2026-11-12.142l'
```

**Why this exists:** until .142c all five builders carried a hard-coded
stamp. After four releases the shipped PDFs still claimed `.136ai`
(9 November) — the staleness was invisible because nobody diffs a PDF.
Now a document *cannot* be older than the code it documents. If you add a
document, stamp it from `r2_version`, never by hand.

---

## D. The web UI

Covered above (group A) — listed again because it has its own install path
(`web/install_web.sh`) and its own test battery (`r218_webui_check.py`,
25 checks pinned against field reports).

---

## E. The test net — and what each part proves

This is the part the MANUAL never mentions, on purpose: none of it ships.
It exists so that a claim like "the texture is seamless" is a measurement,
not an opinion.

### E1. The six tiers (`tools/r198_tier_report.py`)

`python3 tools/r198_tier_report.py [--tier normal|power|developer|hardcore|stress|function|all]`

| Tier | Runs | Proves | Last run |
|---|---|---|---|
| **normal** | `r141_journeys`, `systemtest`, `config_validator`, `r165_doc_check` | the printer behaves as a human drives it; the config is sane; **the docs match reality** | 2 481 + 214 + 0 err + clean · 4 pass / 0 fail |
| **power** | `megatest`, `r110_setup_sim`, `r142_field_coverage`, `r143_user_audit`, `r166_template_check`, `r168_stampcheck`, `r164_serial_budget` | every generator end to end; install/update scenarios; every field-reported bug pinned; Klipper-parse + Jinja compile of all 399 templates; stamp fit; serial/timeout budget | all pass |
| **developer** | `macro_render_test`, `r81_golden_check`, `r111_geom_test`, `r167_aircheck` | **2 046 menu/macro renders**; byte-identical postproc goldens; geometry classifier; bridge air scan | 2 046/2 046 · 23/23 |
| **hardcore** | `r190_tag_ladder`, `r197_gen_sweep`, the `r2xx` field-pin family, `r199_zip_check`, `audit_sweep` | feature tagging at five levels; all generators × parameters + tools; historical field rounds stay fixed; release-zip layout | all pass |
| **stress** | `r140_stress` | 46 000-check endurance run | pass |
| **function** | `r187_matrix`, `systemtest` | workflow matrix across printer modes | pass |

**Release gate order (what I run before a zip):** `r166` (does it even
compile) → `macro_render_test` (does every menu render) → field checks
(`r142`/`r218`/`r235`/`r236`) → `r81` (did generated output move) →
`r165` (do the docs still tell the truth) → `r199` (is the zip sane) →
`r198 --tier all`.

### E2. The field-log pin family (`r2xx_*`)

Every field report that reached this project got its own permanent check
file, named after the round that fixed it: `r215_field_fixes`,
`r226_field_fixes`, `r228_pause_storm`, `r234_field_check` …
`r244_field_check`. Each one replays the field log's exact scenario and
asserts the fix. **They are the memory of the project** — when a bug
reappears, one of these goes red instead of the user finding out mid-print.

### E3. Audits that measure rather than claim

| Tool | Measures |
|---|---|
| `r142_field_coverage.py` | 142 checks — every field-reported bug has a pin (currently 142/142) |
| `r143_user_audit.py` | 68 checks — can a user find, use and understand each feature |
| `r164_serial_budget.py` | the MCU serial budget — the "Timer too close" firewall |
| `r167_aircheck.py` | physically: do generator paths bridge over air |
| `r168_stampcheck.py` | stamp/contour/mirror fit, in millimetres |
| `r165_doc_check.py` | every macro named in the docs exists; every LCD path in the docs exists in the menu tree |
| `r166_template_check.py` | Klipper-parse + Jinja compile of every template (the way Klipper does it, not the way we hope) |
| `r142_spell_lint.py` | spelling of user-facing strings (a hint lint — deliberately not a gate) |
| `systemtest.py` | system files + install integrity (214 checks, 26 files) |
| `audit_sweep.py` / `megatest.py` / `r197_gen_sweep.py` / `r140_stress.py` | generator invariants, parameter extremes, endurance |
| `r110_*`, `r111_*`, `r190_*`, `r187_*` | g-code dialects, geometry classifier, tagging ladder, workflow matrix |
| `macro_render_test.py` | the render harness itself: full printer-object simulation (KAMP present/absent, unhomed axes, paused, missing objects…) |
| `r81_golden_check.py` | byte-level regression net for the post-processor's two core functions |
| `test_toolchain.py` / `test_toolchain_steps.py` | the chain engine: 49 tests (plan validation, §22.4 temp adoption, on_output gate semantics, on_step start semantics + cosmetic rule) + 22 adapter/registry tests incl. the wiring guard (the watcher really passes `on_step`) |

### E4. Fixtures

`testfixtures/` — small real-world g-code files the render harness needs
(dialects, arc-fitted vases, marker-less files). `tools/r223_fixture.jpg`,
`fonts_src/` — label font sources. None of it ships.

---

## F. Coverage status (what is documented where)

| Group | In MANUAL | In this file | Status |
|---|---|---|---|
| Generators (21 tools) | ✅ every one has a chapter (§5.1–5.20) | summary | complete |
| Texture patterns | ✅ 27-pattern table with use cases (§5.9) | summary | complete |
| Core runtime (group A) | ✅ behaviour only | ✅ mechanics | complete |
| Install/update (B) | ✅ Appendix A/C | ✅ | complete |
| Doc builders (C) | ❌ intentionally | ✅ | complete |
| Test net (E) | ❌ intentionally (DEVELOPMENT.md instead) | ✅ | complete |

## G. Findings from the .142c documentation round (fixed and pinned)

Five staleness classes were found — and each one now has a check:

| Finding | What it was | Now |
|---|---|---|
| **PDF stamps** | All five documents claimed `.136ai` (9 Nov) after four releases — the stamps were hard-coded and nobody diffs a PDF. | `tools/r2_version.py` is the single source; `r165` fails on any hand-typed stamp. |
| **MANUAL pattern count** | Said "21 patterns on 3 pages"; the code has 27 on 4 pages, and five patterns had no name in the docs. | Full 27-row table with use cases in §5.9; `r165` cross-checks the count against `variable_tx_codes`. |
| **TEXTURING.pdf coverage** | The builder skipped every pattern without a library preset (`if not ps: continue`) while its build message counted 27 — the six R238 patterns (Knit, Fluted, Bark, Scales, Facets, Macrame) had no page at all. | 33 pages, all 27 documented; preset-less patterns are illustrated with the tool's defaults and the message names how many ship a ready look (21). |
| **DEVELOPMENT.md + tier text** | Claimed "1247 tests" / "1.910 renders" while the suite runs 2046. | Both corrected. |
| **MANUAL.md vs MANUAL.pdf** | ⚠️ **Still open.** `make_manual_pdf.py` does *not* read MANUAL.md despite its docstring claiming it mirrors it — it is a hand-maintained second copy (≈2 950 lines of flowables). Both are current as of .142c, but an edit to one does **not** reach the other. | Documented here; the .142c round updated both by hand. Unifying them is the next documentation round. |

**Known open items:**
1. `MANUAL.md` ↔ `MANUAL.pdf` divergence (above) — the PDF must be rebuilt by
   hand-editing the builder. The honest fix is to generate the PDF text from
   the markdown, or to declare MANUAL.md the source and drop the duplicate.
2. The MANUAL's generator chapters describe *parameters and workflows*; a
   per-generator "how it is built" paragraph (geometry math, placement
   rules) lives only in the code docstrings.

---

## H. Emergency & triage (added .142c, R246f)

Two scripts exist purely so that a field problem costs **minutes, not days**:

| Script | Purpose |
|---|---|
| `tools/r256_drift_audit.py` | **Drift audit — "Pre-Print says A, Live says B".** Static data-flow proof over all 2295 LCD rows: every numeric read-out is mapped to the variable that feeds it. It reports a shared name fed by two different macros, a row whose text names one quantity while reading another, a shown variable nobody writes, and a variable name declared by two macros. Current result: 335 shown variables, all of them written, no double source. |
| `tools/r257_crash_guard_check.py` | **15 checks + 7 counter-tests — pins the PROBE-QUIET LED guard (R257).** `G28`, the mesh block, the screws flow and `PROBE_CALIBRATE` mute the LED animation for the duration of the motion (`_LED_QUIET`), `SET_LED_STATE` only records the wanted state while muted, the watcher heals a stuck mute. The counter-test deletes each guard in turn and requires the run to fail - a check that cannot fail is decoration. Field evidence: 6 of 8 MCU shutdowns sat at the `[safe_z_home]` XY with the toolhead mid-descent. |
| `tools/r255_homing_guard_check.py` | **18 checks — pins the HOMING GUARD (R255).** The G28 wrapper marks every homing as `mode='homing'`, every motion gate has its own print_time sample, the selection preview defers instead of firing into a probe, the object-polygon payload is capped, the SD write is out of the homing block; plus a functional test of the probe answer (mode homing + still head = moving). |
| `tools/r2_emergency.sh` | **Get printing again.** Stops the watcher service, sets `mesh_mode = "OFF"` (the seam where the crash fires: our start macro runs the mesh calibration directly after `G28`), optionally removes the web extension (`--web-off`), restarts Klipper. Every change is backed up with a state file — `--revert` puts everything back exactly. `--status` shows what is on/off without changing anything. |
| `tools/r2_triage.sh` | **Collect everything in ONE file.** Version actually installed, host health (RAM/swap/throttle/load), service states, the emergency state, every load-relevant `printer.cfg` section, the last crash context from `klippy.log` incl. the reactor-stall lines, the watcher journal, the web-extension state, and a short self-assessment summary. Changes nothing. |

**The rule these enforce:** before any fix is built, the question "is it us
or the machine?" must be answerable in one command. `r165` fails if either
script stops parsing or loses a path.

---

## I. The menu test (R246h)

`tools/r2_menu_test.sh --off|--on|--status` switches
`menus/lcd_menues.cfg` out of `printer.cfg` (backup + exact revert).

**Why it exists:** every "Timer too close" field log shows the reactor stall
containing `MenuManager.dispatch_gcode (menu.py:952)` next to two
`DelayedGcode` events and two webhook queries. Klipper re-evaluates menu name
**templates** on every refresh; this menu file is 20 237 lines with 2 423
menu sections and **483 dynamic name templates**. That is the largest
synchronous block the reactor can hit — and it survives stopping the
post-processor daemon, because menus are evaluated *inside* Klipper.

Safe because the file contains exactly one macro, the version sentinel
`_V16_MENUS`. Nothing in the print flow depends on it.

---

## I. The menu test (R246h)

`tools/r2_menu_test.sh --off|--on|--status` switches
`menus/lcd_menues.cfg` out of `printer.cfg` (backup + exact revert).

**Why it exists:** every "Timer too close" field log shows the reactor stall
containing `MenuManager.dispatch_gcode (menu.py:952)` next to two
`DelayedGcode` events and two webhook queries. Klipper re-evaluates menu name
**templates** on every refresh; this menu file is 20 237 lines with 2 423
menu sections and **483 dynamic name templates**. That is the largest
synchronous block the reactor can hit - and it survives stopping the
post-processor daemon, because menus are evaluated *inside* Klipper.

Safe because the file contains exactly one macro, the version sentinel
`_V16_MENUS`. Nothing in the print flow depends on it.

## F. Offline analysis & reverse engineering (never runs on the printer)

The Masterkonzept toolchain. It reads a G-code file read-only and writes a
JSON sidecar; it never mutates the file, never emits move commands and
never claims physical print safety. Ships in the package for offline use
(e.g. on a PC or the Pi when idle) — nothing in this group is wired into
the live print path.

| File | Lines | What it does |
|---|---|---|
| `tools/gcode_re.py` | 884 | **The unified Masterkonzept Pass 0-11 pipeline (v3).** One streaming pass over the source: Pass 0-2 via the verified shadow parser (modal state, fail-closed), Pass 3-10 evidence via the tracker (layers/kinematics/topology/tag-audit G-codes), plus real vector Pass-6 geometry: Z-plane buckets (gap-clustered, default 0.05 mm), endpoint-tolerant **online loop extraction** (rings emitted mid-chain, so branches off a junction do not break the ring), shoelace area, nesting hierarchy from ray-cast point-in-polygon, open-hatch direction histogram + median-gap spacing estimate (`RECTILINEAR_LIKE`/`GRID_LIKE`/`UNKNOWN_PATTERN`). Pass 8 feature scoring v2: multi-signal evidence with **top-3 hypotheses, explicit UNKNOWN/AMBIGUOUS, `calibrated: false`, bounded weights in a documented table** — scores are never probabilities. Pass 10 conservation audit (line accounting, extrusion filament shadow-vs-tracker). Pass 11 sidecar (`r2-re/2`): written atomically, existing destination refused unless `--force`, input opened read-only with sha256 in the provenance block. `--with-moves` embeds compact move records (capped). Measured on the 5 MB `rose_215c_pla` fixture: 156 948 lines -> 156 948 records, extrusion ratio shadow-vs-tracker 1.0, 480 rings found, ~25 s on the sandbox CPU. Honest limits: ultra-adaptive/non-planar prints merge many Z levels into few plane buckets (documented); support/prime-tower/raft roles are NOT inferred. |
| `tools/r2_offline.py` | 400 | The earlier one-pass evidence report/audit/derive CLI (`report` / `audit` / `derive`) — atomic, source read-only, derive never overwrites. `r2_offline.py report` stays the stable minimal path; `gcode_re.py` is the full Masterkonzept pipeline. |
| `tools/r2_analysis.py` | 1 045 | Pass 3-10 evidence tracker used by both: units/layers, vase detection, kinematics + volumetric flow, footprints, 2D closed-loop nesting (bbox), 3D support grid, sequence audit (C2/C3), tag-vs-geometry audits G1-G6, pattern *metadata* (not geometric recognition). |
| `tools/r2_shadow.py` | 547 | Pass 0-2 modal state machine. Fail-closed: unknown/unsupported commands invalidate XYZ/E/feed until re-declared. Opt-in: arcs (G17 I/J), firmware retract, Klipper-passive sets, verified R2 markers, inch units. |
| `tools/test_gcode_re.py` | 218 | 10 tests: loop symmetry, nesting depth, hatch statistics (spacing 2.0 mm at 2 mm strokes), UNKNOWN stays UNKNOWN, G28 restore semantics, hash preservation, atomic sidecar + refuse-overwrite, `--force`, suffix enforcement, move-record cap. |
