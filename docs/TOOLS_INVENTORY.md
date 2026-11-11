# Tools inventory — what is what, and what proves it

*Stand: R2-2026-11-11.142c (R246d). Auto-checked against reality by
`tools/r165_doc_check.py`; the version line here is not typed by hand —
see "The version rule" below.*

This page answers the question the MANUAL deliberately does not: **the
MANUAL describes what the printer does, this describes the machinery that
makes it do it.** 73 files, ~77 600 lines, in five groups. Everything in
group A ships to the Pi and runs during a print; everything in group E
never leaves the repository.

---

## A. On the printer — the core runtime (ships)

| File | Lines | What it does |
|---|---|---|
| `tools/r2_postproc.py` | 28 221 | **The engine.** One systemd service, four jobs: (1) the *layer reader* — tags every new g-code with `LAYER_MARK`/`APPLY_TYPE` markers, a `;TYPE:` map and a `_FILE_INFO` block, so the LCD, the menus and the live tuning know what is printing before layer 1; (2) **every generator** (range, labels, plotter, cable ties, angles, lithos, gaskets, frames, bricks, kits, figures, colorpic, string art, geometry, scale/taper/twist, mirror, STL export, cake cut) — the LCD only sets variables, the real work happens here, off the print thread; (3) the *watcher* — folder watching, preview pushes, queue handling, the recovery tick; (4) **HOST_CHECK** (throttle, load vs cores, swap *activity*, hidepid honesty) and the MCU auto-recovery. Streaming, one line in / one line out — no full-file buffers (a full buffer is what kills the Pi's RAM and then the print). |
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
| `tools/r2_version.py` | **Not a builder — the version rule.** |
| `tools/make_label_fonts.py` | Build-time helper for the embedded label fonts. Never needed on the Pi. |

### The version rule

`tools/r2_version.py` reads the release string from `macros/01_state.cfg`
(the same string the LCD shows and `r199_zip_check.py` verifies) and every
builder stamps its pages from it:

```python
from r2_version import VERSION as _R2VER     # 'R2-2026-11-11.142c'
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
| `tools/r2_emergency.sh` | **Get printing again.** Stops the watcher service, sets `mesh_mode = "OFF"` (the seam where the crash fires: our start macro runs the mesh calibration directly after `G28`), optionally removes the web extension (`--web-off`), restarts Klipper. Every change is backed up with a state file — `--revert` puts everything back exactly. `--status` shows what is on/off without changing anything. |
| `tools/r2_triage.sh` | **Collect everything in ONE file.** Version actually installed, host health (RAM/swap/throttle/load), service states, the emergency state, every load-relevant `printer.cfg` section, the last crash context from `klippy.log` incl. the reactor-stall lines, the watcher journal, the web-extension state, and a short self-assessment summary. Changes nothing. |

**The rule these enforce:** before any fix is built, the question "is it us
or the machine?" must be answerable in one command. `r165` fails if either
script stops parsing or loses a path.
