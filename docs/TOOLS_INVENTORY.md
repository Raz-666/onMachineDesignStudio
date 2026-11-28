# Tools inventory — what is what, and what proves it

**Shutdown register:** `docs/SHUTDOWN_REGISTER.md` — every crash site,
its cause, its fix and the test that holds it, in one table.

*Stand: R2-2026-11-19.3 (R285). Auto-checked against reality by
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
| `tools/r2_postproc.py` | 35 091 | **The engine.** One systemd service, four jobs: (1) the *layer reader* — tags every new g-code with `LAYER_MARK`/`APPLY_TYPE` markers, a `;TYPE:` map and a `_FILE_INFO` block, so the LCD, the menus and the live tuning know what is printing before layer 1; (2) **every generator** (range, labels, plotter, cable ties, angles, lithos, gaskets, frames, bricks, kits, figures, colorpic, string art, geometry, scale/taper/twist, mirror, OBJ export, cake cut, spray stencils) — the LCD only sets variables, the real work happens here, off the print thread; (3) the *watcher* — folder watching, preview pushes, queue handling, the recovery tick; (4) **HOST_CHECK** (throttle, load vs cores, swap *activity*, hidepid honesty) and the MCU auto-recovery. Streaming, one line in / one line out — no full-file buffers (a full buffer is what kills the Pi's RAM and then the print). **R286 CONF-Dynamik:** jedes getaggte Feature trägt `CONF` — Slicer-Tag = autoritativ (1.0); abgeleitetes Feature = `0.5+0.5·Abdeckung−0.08·Konflikte`, Floor 0.3, Cap 1.0, Ziel 1.0 (fester 0.7 nur als Basis-Referenz). **Ableitung:** Ironing (S2: SURFACE-TOP + INFILL im selben Layer) und PRIME-TOWER (S5: ≥4 dichte Schichten ab L1, kein Sparse-Infill) werden als INFERENCE abgeleitet, nicht nur aus dem Slicer-Tag gelesen; Reihenfolge der Features = weiches Signal. **R286 MCU-OPTIMIZATION:** `_GenE.line()` verschmilzt kollineare Folge-Moves (gleiche Richtung, Feed, E-per-mm) zu einem G1 — reduziert MCU-Command-Count beim Druck. **R287 PIC-Vorschau:** nach jedem erfolgreichen Processing wird (best-effort, nicht breakend) automatisch ein Bildvorschau-G-Code mit `_PIC`-Suffix im selben Ordner erzeugt; der Watcher scannt `_PIC`-Dateien nicht (PIC-Skip in Processing + Census). **R286/R290 Nozzle-Clean:** der Düsenreinigungs-Switch (`nozzle_clean_on`, Default ON) löst `_PURGE_SMART` → `_NOZZLE_WIPE` im Print-Start aus; eine separate 11b-Duplikat-Block wurde entfernt. **R231 make_range-End-Clamp:** `end = min(end_raw, len(marks))` sichert, dass `range end>total` auf kleinen Dateien sicher refuset (Regression-Fix, R2-2026-11-26.6). |
| `tools/r2_postproc_next.py` | 35 670 | **The experimental copy.** Byte for byte `r2_postproc.py` at the moment of R252, plus its own header. From now on new post-processor work happens HERE and the stable file is not touched. Never started directly: the service starts the stable file, which reads the pp_engine switch (LCD System > PP engine, variables file) and hands over via runpy when it says `next`; a syntax error or a crashed handover keeps the stable engine and brakes the switch for 15 min. **R286:** BLUR-Parameter (`texture_blur`) + MCU-Segment-Merge in `_GenE.line()` integriert. **Make_Range-Spiral-Fix** (PRE-PASS-Spirale-Synthese + R231-End-Clamp) in beiden Engines portiert. |
| `tools/toolchain.py` | 1 256 | **The chain engine (R259).** `plan_chain()` turns a preset file (JSON, `presets/toolchain/` + the gcodes `Toolchain/` folder) into a validated step plan - tool registry, parameter schema, file-name globbing, honest refusals (unknown tool, missing file, empty plan = `[]`). `run_chain()` executes it streaming: per-step temp workspace (`§22.4` - a step's temp is deleted the moment the next step adopts it), optional `validator`, `output_mode='save'`, `cancel_check`, the `on_output` gate (every artifact passes through it before it becomes the next step's input) and `on_step` progress (R261: fires at step START, cosmetic - a broken hook can never kill a chain). |
| `tools/toolchain_steps.py` | 304 | **The real adapters.** Each supported tool as one `Step` (command, param mapping, produces/consumes). The registry is the single place that decides what is chainable - and what is not (the cake cutter refuses: it is a hand-over cut, not a file-to-file transform). |
| `tools/r2_collect.py` | 383 | **The evidence pack ('Doctor').** Builds ONE support file: build stamps, host (RAM/swap/disk/load/top/throttled/dmesg), the three services + journals, the watcher state files, variables.cfg, printer.cfg, a compact incident digest out of klippy.log (events, the worst Reactor stalls WITH stacks, MCU statistics around each shutdown), the last 3 MB of the raw log, the newest MCU snapshot, the gcodes inventory. Writes gcodes/crash_archive/R2-DOCTOR-<stamp>.txt + a .txt.gcode twin (Mainsail only lists printable files) - the post-processor skips every R2-DOCTOR-* name. Idle-gated, read-only, no sudo. Started by the LCD (System > Diagnostics), by the watcher (doctor_nonce) or by hand. |
| `tools/r2_texture.py` | 3 657 | **The texture engine** (called by r2_postproc, also standalone): FUZZY (Orca-style fuzzy skin), BUMPS (**113 seamless patterns**, deep relief up to 4 mm — E rides the real path) und MAP (a picture wrapped around the part). Rewrites only the outer wall of an existing file — `;TYPE:`, E/Z/F and EXCLUDE_OBJECT stay byte-identical. **R286:** BLUR-Parameter (Gauss-Weichzeichnung, 0–2.0) in `apply_texture` + `pattern()`; `_MergeWriter` verschmilzt kollineare G1-Moves — reduziert MCU-Command-Count. **R231 ARC-ANCHORED Mapping:** `s` wird bogen-verankert (Loop-Länge statt reiner Winkel-Fraktion) — Musterzellen behalten auf konkaven Sections (Vasen-Nocken) ihre physikalische Größe statt zu strecken; interne Engine-Technik, **keine printer.cfg-Option**. **R236 Spiral-Vase-Z-Zählung:** über den R231 Loop-Pre-Pass-MEDIAN (echter Durchmesser), nicht über Move-Count. **R290 pro-Objekt-Textur:** `EXCLUDE_OBJECT_START/END`-Blöcke teilen die Geometrie — jedes Objekt bekommt sein eigenes Zentrum (aus `EXCLUDE_OBJECT_DEFINE CENTER`), Umfang, Höhe, Loop-Längen und Pattern; Pass 2 wechselt den Kontext pro Objekt und resettet die Anfahrtsrichtung (px/py). Einzelobjekt-Dateien bleiben byte-identisch (kein Kontextwechsel). Variable Schichthöhe wird über absolutes Z korrekt gehandhabt. |
| `tools/r2_cake.py` | 963 | **The cake-cut engine**: splits a print with a plane, E redistributed per section. |
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
| `tools/make_manual_pdf.py` | `MANUAL.pdf` (113 pages, R2-2026-11-19.2) — the illustrated handbook (incl. §5.17–5.22 Twist/Geometry/STL/Mirror/Toolchain/Casting molds + updated §25 index). |
| `tools/make_texture_pdf.py` | `TEXTURING.pdf` (64 pages) — the full pattern catalog, every pattern sampled from the real pattern functions, plus the preset mapping. |
| `tools/make_feature_pdf.py` | `FEATURE_TAGGING.pdf` (14 pages) — the `;TYPE:`/layer-marker system in depth. |
| `tools/make_displays_pdf.py` | `DISPLAYS_WEB_UI.pdf` (11 pages) — behaviour with other displays / Mainsail / web UI. |
| `tools/make_cakesplit_pdf.py` | `CUTSPLIT.pdf` (7 pages) — the cut & split methodology. |
| `tools/make_scale_pdf.py` | `SCALE.pdf` (6 pages, R2-2026-11-19.2) — Pre-Print modifier **Scale X/Y & Z-Taper** mathematics & blind operation (D4/D6): anisotropic XY affine map, extruding-span Z-taper (`ezmin..ezmax`), directional extrusion factor `k_E(θ, z) = (L'/L)·(w'/w)`, G2/G3 chord flattening, 6 live LCD rows, rotary-click & mental-math guide, and 2 figures + 5 benchmark runs from real `apply_scale()` calls. |
| `tools/make_twist_pdf.py` | `TWIST.pdf` (6 pages, R2-2026-11-19.2) — Pre-Print modifier **Twist** mathematics & blind operation (D4/D6): `SO(2)` helical Z-rotation, Euclidean isometry proof (`det R = +1 -> E verbatim`), circumscribed-circle bed guard `2·R_circ`, overhang shift nomogram `|DEG|_max ≈ 63·H/r`, 3 live LCD rows, and 2 figures + 5 benchmark runs (`ΔE = 0.00000`) from real `apply_twist()` calls. |
| `tools/make_mirror_pdf.py` | `MIRROR.pdf` (5 pages, R2-2026-11-19.2) — Pre-Print modifier **Mirror** mathematics & blind operation (D4/D6): in-place reflection `2·c - p`, bbox self-invariance proof, `det M = -1` arc chirality reversal, R239 compact KAMP `POLYGON=` mirroring, R224 selective `OBJ=<name>` multi-object flip, 3 live LCD rows, and 2 figures + 5 benchmark runs from real `apply_mirror()` calls. |
| `tools/make_range_pdf.py` | `RANGE.pdf` (6 pages, R2-2026-11-19.2) — Pre-Print modifier **Range / Stop** mathematics & blind operation (D4/D6): runtime `Stop@` vs. `make_range()` excerpt, global `dz` bed-anchoring, R224 seamless in-window replacement (`inside=1`), `FOOTPRINT` convex hull vs. `OUTLINE` flood-filled mask + bossed holes, `O(1 Layer)` streaming, 15 live LCD rows, caliper-to-layer mental math, and 2 figures + 5 benchmark runs from real `make_range()` calls. |
| `tools/make_toolchain_pdf.py` | `TOOLCHAIN.pdf` (6 pages, R2-2026-11-19.2) — Pre-Print modifier **Toolchain & Live-Offset** mathematics & blind operation (D4/D6): operator composition `(T_n ∘ ... ∘ T_1)(G_0)`, commutator `[R(α), S]` non-commutativity proof (`Scale -> Twist != Twist -> Scale`), canonical 5-stage order, `r2-toolchain/1` schema & §22.4 atomic `Vnn_` handoff, distinction from live `Offset X/Y/Z` (`SET_GCODE_OFFSET`), live LCD tables, and 2 figures + 4 chain runs from real `toolchain.run_chain()` calls. |
| `tools/make_molds_pdf.py` | `MOLDS.pdf` (11 pages, R2-2026-11-19.2) — the casting-mold generator methodology & parameter reference (D3/D6): 2D silhouette rasterization, mating-face-up Y-mirror + dowel registry math, undercut proof, cell-quantized draft erosion curve, 3-/4-part sector cuts & 25 mm bridge cap, STANDARD/FINE/FUZZY surfaces, MEDALLION/PLAQUE/BAR parametric blanks + flush relief-seat boss math, 34 live LCD rows read from `menus/lcd_menues.cfg`, and 4 figures + 5 benchmark rows computed live from `make_mold()` / `make_mold_blank()` at build time. |
| `tools/make_stencil_pdf.py` | `STENCIL.pdf` (6 pages, R2-2026-11-19.2) — the spray-stencil generator methodology & parameter reference (D3/D6): percentile tone-band partition `B_k`, R267 `< 2 %` plate-reduction guard, 8-neighbour flood-fill island detection `_stencil_bridges267()` + `3× nozzle` (`1.2 mm`) horizontal keeper bridges, congruent `4× D4.2 mm` M4 registration holes (`ΔXY = 0.0000 mm`), `Negativ = ON` silhouette plate, live LCD rows from `menus/lcd_menues.cfg`, and 2 figures + 5 benchmark sets computed live from `make_stencil()`. |
| `tools/make_lithophane_pdf.py` | `LITHOPHANE.pdf` (7 pages, R2-2026-11-19.2) — the lithophane & relief-stamp generator methodology & parameter reference (D3/D6): Beer-Lambert transmission `I(t) = I_0·e^(-μ·t)` across `0.70..3.00 mm`, `_litho_grid()` 7-stage pipeline, `STANDING` single-track `ribbon()` (`0` retracts/travels) + R214 breakaway triangular stands `LITHO_STAND_L/R`, `FLAT` nested terrace plateaus with `OFF/LAST/EACH` M600 color swaps (`PURGE_TOWER`) & `Contour 0..3` outline rings, R168 `_StampFit168` snap-in relief stamps (`Vnn_Stempel` + `Vnn_Griff`), live LCD rows, and 2 figures + 6 benchmark runs computed live from `make_lithophane()`. |
| `tools/make_colorpic_pdf.py` | `COLORPIC.pdf` (5 pages, R2-2026-11-19.2) — the multi-color relief poster generator methodology & parameter reference (D3/D6): nested luminance plateaus `Ω_0 ⊇ ... ⊇ Ω_{B-1}` (`100 %` support, `0` overhang), `_blocks120` scanline RLE, all 14 `COLORPIC_PALETTE` RGB codes & `COLORPIC_DEFAULTS[2..8]` ramps, LED-guided `_COLORPIC_SWAP + M600` + R149 `pen.set_z(z)` reset + `12×12 mm` `PURGE_TOWER` + cap `IRONING`, live LCD rows, and 2 figures + 5 benchmark runs (incl. exact per-spool filament mm/g) computed live from `make_colorpic()`. |
| `tools/make_stringart_pdf.py` | `STRINGART.pdf` (6 pages, R2-2026-11-19.2) — the free-air string-art generator methodology & parameter reference (D3/D6): `SPIRAL` cardioid/nephroid caustic `r_env = R·cos(π·step/N)` vs. `PHOTO` greedy inverse-Radon chord planner `_string_art_plan()` (`n_cand = 240`, `min_chord = 0.18·N`, `_spread_starts >= 15°`), 6-band `LADDER` (`+0.20..+0.95 mm`), non-planar sinusoidal bow `z_band + Bow·sin(π·t)`, 6-vertex anchor wrap curl (`r = 0.30 mm`), R216 ultra-thin string flow `E/mm = wid·0.068/A_fil`, `Frames`-compatible `ROUND`/`RECT` presets, live LCD rows, and 2 figures + 5 benchmark runs computed live from `make_string_art()`. |
| `tools/make_bricks_pdf.py` | `BRICKS.pdf` (7 pages, R2-2026-11-19.2) — the building-bricks, BrickKit & figures generator methodology & parameter reference (D3/D6): `8.0 mm` pitch & `n·8.0 - 0.20 mm` clamp body, `9.6 mm = 3× 3.2 mm` height law, hollow `Ø4.8×1.8 mm` studs & tangential `Ø6.31 mm` underside tubes (`sqrt(2)·8.0 - 4.8 = 6.514 mm`), 76 catalog codes across 8 families, R216 `scale=200/300` `+1/+2` wall-loop rule, `BY_LAYER` (`0× M600`) vs. `BY_OBJECT`, `make_brick_kit()` voxelizer + step-edge slope replacement, `make_figures()` 5-part snap-fit (`PARTS` with lying arms) vs. `SINGLE`, live LCD rows, and 2 figures + 6 benchmark runs. |
| `tools/make_labels_pdf.py` | `LABELS.pdf` (6 pages, R2-2026-11-19.2) — the label, face-down inlay & text-stamp generator methodology & parameter reference (D3/D6): 8 embedded vector stroke fonts (`SMOOTH..PLATE`) with R183 swash collision guard (`advance >= max(x_ink) + 0.15`), multi-line mitered `_stroke_offsets()`, `GROW` vs. `FIXED` auto-fit + `OVAL`/`ROUND` inscribed text box, R170 multi-plate `_T1/_T2` split, R231 anchored `text_layers` (`2` flush + `3..4` raised), `Flip=ON` PEI face-down inlay, R168/R170 `_StampFit168` stamps (`handle=0..3`), live LCD rows, and 2 figures + 6 benchmark runs. |
| `tools/make_frames_pdf.py` | `FRAMES.pdf` (5 pages, R2-2026-11-19.2) — the picture-frame & display-case generator methodology & parameter reference (D3/D6): zero-overhang front-up profile (`P_w = W + 1.6 mm` R127 guillotine play, `V_w = W - 3.0 mm` bridged shelf, `1.2 mm` front disc lip), `FLAT` (`< 15 mm`) vs. `CASE` (`>= 15 mm` + `cable=ON` LED duct), `BACK` snap-in brimless backplate (R115) vs. `SIDE` slot, 5 front modes (`IRON`/`FLIP`/`LINES`/`WAVES`/`HEX`), 7 presets + R90.1a `Part A / Part B` split, live LCD rows, and 2 figures + 5 benchmark runs. |
| `tools/make_plotter_pdf.py` | `PLOTTER.pdf` (5 pages, R2-2026-11-19.2) — the 2D pen & filament plotter methodology & parameter reference (D3/D6): cold `PEN` vs. heated `FILAMENT` (`E/mm = fil_z·0.65/A_fil`, `d <= 2.2 mm` flat bridge vs. `G10/G11` hop, `80 mm/s` travel cap), R64 dark-board auto-polarity + R62 Otsu white threshold, `Mode 0` boustrophedon hatch vs. `Mode 1` stipple dots, SVG Bezier/PDF vector & `text_convert()` multi-column page layout, `make_plot_cal()` (`100×140 mm`, 63 dots + 27 strokes), `R2PLOT` KAMP capsule & `_PLOT_END` reset, live LCD rows, and 2 figures + 5 benchmark runs. |
| `tools/make_angles_pdf.py` | `ANGLES.pdf` (6 pages, R2-2026-11-19.2) — the L-angle, miter & flat-splice connector generator methodology & parameter reference (D3/D6): 6-vertex concave chevron polygon (`30°..170°`) vs. `FLAT` (`180°` mirrored-hole splice strip), `>= 3.0 mm` edge-clearance hole auto-clamp (`d_max = min(width - 6, 10)`) & auto-reduction, 2-step `Countersunk` (`1.5×d / 2.0×d`) + R95 bore retract guard, `Gusset` & 2-tier `Stepped` corner ribs, concave `_poly_hatch()` (`max_conn <= 3.0 mm`), `My presets`, live LCD rows, and 2 figures + 5 benchmark runs. |
| `tools/make_cableties_pdf.py` | `CABLETIES.pdf` (6 pages, R2-2026-11-19.2) — the self-scaling cable-tie generator methodology & parameter reference (D3/D6): strap bending-strain law `ε_max = t_strap / (2·R_min)`, `CLASSIC` compact one-way ratchet (`slot_w = width + 0.50 mm`, `+0.6 mm` shifted 2-layer sawteeth, cantilevered ceiling `Pawl`) vs. reusable `LOOP` frame + lateral 45° snap beads (`+0.5 mm/side`), head-only brim, R96 slot keep-out `pen.hole_polys`, R197 honest `TYPES=`, `TIE_1..TIE_n` objects, live LCD rows, and 2 figures + 5 benchmark runs. |
| `tools/make_gaskets_pdf.py` | `GASKETS.pdf` (5 pages, R2-2026-11-19.2) — the zero-seam spiral gasket generator methodology & parameter reference (D3/D6): continuous Archimedean spiral `band_pts()` (`Δr = 0.95·wid`, alternating `out_in` per layer, `0` radial seams), `FLAT` vs. `NUT` (`GROOVE`) dual-lip geometry (`2× 30 %` lips + `40 %` groove -> exact `A_NUT = 0.60·A_FLAT`, `1.67×` contact pressure), `w_r` narrow-band refusal & honest `NUT->FLAT` auto-fallback, R96 groove retract disc, `15 %`-flow spiral ironing, live LCD rows, and 2 figures + 5 benchmark runs. |
| `tools/make_geometry_pdf.py` | `GEOMETRY.pdf` (5 pages, R2-2026-11-19.2) — the parametric geometry & diagonal bridging calibration methodology & parameter reference (D3/D6): `TRIANGLE` / `SQUARE` / `POLY` (`3..12`) / `CYLINDER` (`48` round or `3..64` segs) with flat-bottom phase `a_0`, affine `_ngon_inset()`, `Walls = 1` true 3D helical `VASE` mode (`0` Z-seam, R217 honest `TYPES=`) + `make_bridge()` 45° diagonal dual-span test (`L_max = min(u_w-t, u_h-t)·√2`, enforced `>= 10 mm` air gap between `BRIDGE_LONG` and `BRIDGE_SHORT`), live LCD rows, and 2 figures + 6 benchmark runs. |
| `tools/make_generators_pdf.py` | `GENERATORS_TOOLS.pdf` (15 pages, R2-2026-11-19.2) — all thirteen generators plus all fifteen file tools (R263: + Toolchain; R267: + Stencil; R275: + Casting molds + verified LCD root paths), one block each: where in the menu, what comes out, **the real LCD rows read out of `menus/lcd_menues.cfg`** (so the page cannot drift), honest limits, one tip. |
| `tools/make_creative_pdf.py` | `CREATIVE_POSSIBILITIES.pdf` (11 pages, R2-2026-11-19.2) — **On-Machine Design Studio for Creative Freedom**: thirteen recipes (R263: + Effektkette/Toolchain) that COMBINE the tools (texture × light, MAP relief, litho+frame+stand, labelled texture, brick structure, string art, scale/twist/mirror variations, cutting, colour, workshop parts, STL round trip, safety tools), plus Modellbau/Deko-Sets/Doppel-Durchgänge chapters, a Fehlersuche-und-Optimierung chapter (symptom → cause → tool), wall-thickness/light tables, what the system deliberately does not do — closing with the commissioned line: „kein PC, kein 3D-Programm, keine KI — nur ein Drehrad.“ |
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
| `r267_stencil_check.py` | the spray-stencil law: tone bands, mask partition, registration-hole congruence, bridge flood (no floating islands), gcode density, determinism (34 checks) |
| `r270_mold_check.py` | the casting-mold law (J2): analytic layer math, equator split, cavity truth measured from the gcode, dowel registry at the same bed position, vent honesty (0 vents + note when the top is too small), draft erosion + gap growth by cavity-cell counters, undercut/bed/pin-fit refusals, all-or-nothing commit, determinism (33 checks) |
| `r271_mold_check.py` | the sector-stage law (J2): 3/4-part molds measured end to end - piece files with piece-local brim/EXCLUDE rect ending at the cut, slide + lift proofs per layer, bridges counted (25mm limit), dowel tunnels proven open in the gcode, honest refusals (both-undercut, trapped middle, frame-blocked slide, over-wide bridge), 2-part regression byte-identical (25 checks) |
| `r272_mold_check.py` | the surface-mode law (J2): STANDARD byte-identical to the default call, FINE irons only the last layer (TYPES token + SPEED_INNER 60->20 + no F3600 print moves + cavity cells unchanged), FUZZY moves wall points off the cell edges (STANDARD: 0 beyond 0.02mm) with max 0.12mm, deterministic, mask untouched; sector combos + wiring quotes (20 checks) |
| `r274_compat_check.py` | the machine-model audit (J7): synthetic foreign printers against the portability contract - config layer (_R2_CONFIG/hardware profile/fallback/legacy warning, nozzle clamp), post-R217 generators on 180/250/300mm beds (in-bed proof, refusals, nozzle scaling with the honest hatch-adaption note), _PRIME_LINE probe-safe window + PRINT_END clamps rendered with Klipper's Jinja dialect on four synthetic machines, docs parity (24 checks) |
| `r275_docs_mold_pdf_check.py` | post-J2 documentation parity + D3/D6 `MOLDS.pdf` truth check: MANUAL.md §5.22 + §25 416-entry index (`r265` 0 unlisted, `r165` clean), `GENERATORS_TOOLS.pdf` 13 generators under `Tools >` + live LCD row extraction, `MANUAL.pdf` §5.17–5.22, `MOLDS.pdf` dynamic `R2VER` + 4 live-computed figures + full shape/surface/split coverage (15 checks) |
| `r290_vsplit_check.py` | the vertical standing-mold law: AUTO/VSPLIT/FLAT routing, exact release-window math (run intersection over x-slabs, equator pick, MID/OFF pinning + honest out-of-window refusal), plate layer counts from the gcode, pour channel open at the top edge, dowel discs empty, hook/thin/master/pocket/sector fallbacks landing on the flat mold with the honest note, refusal atomicity, byte-identical determinism (25 checks) |
| `r286_scalexy_texture_check.py` | the R286 texture + ScaleXY audit: >=90 presets (95), >=2 per texture type (13 V2 families + 30 decorative), all seamless (wrap-jump <= field-jump, MAP image-based excepted), ScaleXY middle scaling active 5%<pos<95%, linear+Bezier bottom->middle->top, bottom/top=1.0x, Engine+Caller+LCD, cfg<->Engine parity 95/95/95 (17 checks) |
| `r286_generator_audit.py` | the R286 L7 generator audit: all 19 generator macros (Shape/Angle/Cable-Tie/Seal/Frame/Labels/Toolchain), valid shapes TRIANGLE/SQUARE/POLY/CYLINDER, parameter validation, _GENERATORS limits, generator sentinel, Frame presets, toolchain contract SCHEMA+registry+drift (15 checks) |
| `r286_label_render_audit.py` | the R286 L3/L5/L6 label render audit: _label_metrics cap_units+baseline, uniform scale (all lines same cap height), lowercase-size conformity, grow/fixed modes + _label_grow_fit, stamp=1+stamp_base, mirror logic R168, Engine-variant parity (10 checks) |
| `r286_watcher_mem_audit.py` | the R286 L8 watcher-memory audit: cache structures bounded (_LABEL_FONT_CACHE/_NOZZLE_CACHE), no unbounded accumulation, no large bytearrays, os.nice CPU relief, measurement method documented; 130 MB idle RAM measurement stays a field check (10 checks) |
| `r286_audio_real_check.py` | the R286 J4/L1 real-audio audit: `tools/r2_audio_play.sh` exists + synthesizes valid 8-bit unsigned PCM mono WAV (22050 Hz); M300 routes klinke/hdmi to `RUN_SHELL_COMMAND CMD=R2_AUDIO_PLAY` (no RESPOND-only host path); M300 beep path (`SET_PIN pwm_cycle_time`) intact; `SET_AUDIO_SOURCE` present; `[gcode_shell_command R2_AUDIO_PLAY]` registered in r2_setup_lib.sh; _SOUND_LIB tunes unchanged; fallback without shell-command extension (9 checks) |
| `r2_midi2wav.py` | **R286 L1 (this round): MIDI/NOTE → 8-bit WAV upsampling (offline, one-shot).** Inputs: `freq:ms` (same as `_SOUND_LIB`), `note:ms` (A4/C#5/Gb3...), or a `.mid` file (standard MIDI, first track, note on/off + tempo). Output: 8-bit unsigned PCM WAV, mono 22050 Hz, square wave + attack/decay envelope - byte-compatible with `r2_audio_play.sh`. **This is NOT the live pipeline** - the upsampling runs once during maintenance; the player then only plays the ready-made WAV (resource-friendly, no real-time synthesis at print time). Usage: `r2_midi2wav.py INPUT OUTPUT.wav`; `--list` shows note names; `--help` shows docs |\n
| `r286_label_texture_geometry_check.py` | the R286 L4/L13 label+geometry audit: L4 label engine renders all 5 lines (L1-L5) into the window (5/5, 49 paths); L13 all 4 make_shape generators (TRIANGLE/SQUARE/POLY/CYLINDER) produce rough-casts with outer-wall blocks that `apply_texture` (BUMPS) engraves (4/4, 200 outer-wall blocks each, 7600-12000 extrusion moves); field check (texture visibility at the print) stays physical acceptance (4 checks) |
| `tools/r287_pic_render.py` | **PIC-Vorschau-Renderer** (reine stdlib). Erzeugt für eine G-Code-Datei eine Bildvorschau (Top-Down + Side-Profile, 900×700 PNG) als `.GCode`-Datei im selben Ordner; Dateiname: Originalname + `_PIC` + `.gcode`. Watcher-Skip (`_PIC` nicht scannen), keine Symlinks, `--cleanup` entfernt stale PICs. Auto-Render-Aufruf in `_work_file281` nach erfolgreichem Processing (best-effort, nicht breakend). |
| `tools/r287_banding_render.py`, `tools/r287_banding_analyze.py` | Diagnose-Renderer (stdlib). `banding_render` erzeugt ein visuelles Banding-Diagramm; `banding_analyze` analysiert die horizontale Banding-Formel des Texture-Engines (Level/Cause). |
| `r276_d4_modifier_pdfs_check.py` | D4/D6 Pre-Print geometry modifier mathematics PDFs (`SCALE.pdf`, `TWIST.pdf`, `MIRROR.pdf`, `RANGE.pdf`, `TOOLCHAIN.pdf`) + R276 `M82+G2/G3` extrusion-sync & single-axis twist/mirror-OBJ fixes: pure-stdlib stream inspection of all 5 PDFs (dynamic `R2VER`, page/image counts, formulas & blind-operation guides), builder version-import rule, `apply_twist`/`apply_mirror` exact `M82` arc `ΣΔE` invariance + header `EXCLUDE_OBJECT_DEFINE` selective flip, and `r2_postproc_next.py` body parity (22 checks) |
| `r277_d3_image_pdfs_check.py` | D3/D6 Paket-1 image/art generator scientific PDFs (`STENCIL.pdf`, `LITHOPHANE.pdf`, `COLORPIC.pdf`, `STRINGART.pdf`): pure-stdlib stream & builder audit (dynamic `R2VER`, `re.split` menu parser with `Schritt` ranges, `<br/>` formula rule, page/image counts, mathematical & blind-operation key terms), live algorithmic engine pins (`make_string_art` bowed 3D strands, `make_stencil` `< 2 %` plate reduction + island bridges, `make_lithophane` `LITHO_STAND_L/R` + `Vnn_Stempel`/`Vnn_Griff`, `make_colorpic` `M600` + `_COLORPIC_SWAP` + `PURGE_TOWER` + `IRONING`), and `r2_postproc_next.py` R252 parity (22 checks) |
| `r278_d3_craft_pdfs_check.py` | D3/D6 Paket-2 craft/design generator scientific PDFs (`BRICKS.pdf`, `LABELS.pdf`, `FRAMES.pdf`, `PLOTTER.pdf`): pure-stdlib stream & builder audit (dynamic `R2VER`, `re.split` menu parser with `Schritt` ranges, `<br/>` formula rule, page/image counts, mathematical & live-menu key terms), live algorithmic engine pins (`make_bricks` `scale=200` 3-loop rule, `make_figures` 5-part snap-fit, `make_labels` R170 multi-plate split + R168 on-plate `GRIFF`, `make_frame` `CASE` + `HEX` + `cable`, `make_plot_cal` + `text_convert` + `plot_convert`), and `r2_postproc_next.py` R252 parity (25 checks) |
| `r279_d3_workshop_pdfs_check.py` | D3/D6 Paket-3 workshop/geometry generator scientific PDFs (`ANGLES.pdf`, `CABLETIES.pdf`, `GASKETS.pdf`, `GEOMETRY.pdf` — completing 13/13 D3 PDFs): pure-stdlib stream & builder audit, 13/13 D3 root-PDF inventory, live algorithmic engine pins (`make_angles` narrow-leg auto-clamp + `FLAT` splice, `make_cable_ties` `CLASSIC` vs. `LOOP` R197 `TYPES=`, `make_seal` `NUT` + narrow-band `FLAT` fallback, `make_shape` `walls=1` 3D Z-helix, `make_bridge` `>= 10 mm` air-gap clamp), docs sync, and `r2_postproc_next.py` R252 parity (25 checks) |
| `r273_mold_check.py` | the blank + relief-seat law (J2 bite 2): parametric MEDALLION/PLAQUE/BAR molds measured - boss cell counts analytic (pi*r^2 per layer), boss wall central in the first cavity layer, nothing central in the last, bar taper narrower at the top than at the foot (taper=1.0 equal), pocket rim/floor/shape refusals, sectors+boss refuse, BOTH adds the base half, master notes the positive, FINE irons the boss half too (22 checks) |
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
