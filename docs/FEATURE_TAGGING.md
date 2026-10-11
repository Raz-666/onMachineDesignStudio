# Feature tagging in G-code — our approach, the community, and how to push the hit rate higher

*Research note (R110, .84). Companion test: `tools/r110_gcode_dialects.py` (12-family
corpus). This file is the honest comparison the owner asked for: what exists in the
community, how our method scores against it, and a concrete roadmap.*

## 0. Status (.85 / R111 — roadmap executed)

Roadmap items **1, 2, 4, 5 and 6 are IMPLEMENTED** in .85; items 3
(fingerprints) and 6-ML (L5) remain documented options on purpose:

| # | Roadmap item | Status in .85 |
|---|---|---|
| 1 | L3+ modal-Z tracking | **done** — Z from travel moves counts; Z-hops never fake a layer (modal semantics: the last Z before an extrusion wins). Dialect corpus proves it (Simplify3D travel-Z family) |
| 2 | Geometry classifier | **done** — closed loops + bbox nesting → walls; parallel straight lines with regular spacing → sparse (≥3 mm) / solid infill; layer-1 solid → bottom, last-layer solid → top; curved paths UNCLASSIFIED; bridges NOT guessed. Only for files with zero `;TYPE:` (first tag disarms) |
| 3 | Movement fingerprints | open (hints would overlap with the classifier; keep for curved paths) |
| 4 | Confidence + cross-checks | **done** — `DERIVED=1 CONF=0.7 COVER=%` in `_FILE_INFO`, honest console wording, tagged always wins |
| 5 | Slicer-config replay | **done** — CFG_KEYS extended to the per-feature set (LW_INNER/SPARSE/SOLID/TOP/SMALL, ACCEL_SOLID/FIRST/TRAVEL, FIL_DIA, TIME_SLOW, SLOW_MIN, FAN_MIN/MAX) |
| 6 | ML layer (L5) | open by decision — the classifier covers the untagged families honestly; ML stays the last 5 % |

Parameters from §6 shipped in .85: feature PA (live + profiled), fan clamp
(min/max + bridge boost), input-shaper-off per feature, unretract extra, flow
cap + travel accel as file fixes, MAXRATE/SEAM display, 14 config keys
replayed. Not shipped (honest): seam control (display only — re-slicing moves
it), per-feature line width (display via LW_* replay), ML.

## 1. What "feature tagging" means here

Given an arbitrary `.gcode` from any slicer/firmware combination, decide for every
move **which print feature it belongs to** (outer wall, sparse infill, bridge, …) and
**which parameters it really used** (speed, accel, line width, temps). Only with that
can a running printer offer per-feature overrides, honest "file original" values in
the UI, or per-file profiles that reproduce a successful print.

## 2. Our method (the R2 post-processor) — four layers

| Layer | Mechanism | Covers |
|---|---|---|
| **L1 dialect table** | 40+ `;TYPE:` spellings mapped to 16 canonical features, per slicer family (Orca/Prusa/SS/Cura/Kiri/AstroPrint/SliceBeam/Elegoo/Bambu…) | every family that writes `;TYPE:` |
| **L2 measurement** | while streaming: modal F + M204 per active feature → `FS_*`/`FA_*` (real speed/accel), line width from config header, `LAYER_MARK` per layer comment | the actual values, not the claims |
| **L3 geometry re-derive** | `APPLY_TYPE` re-derived when a source carries no `;TYPE:` (everything-printed-as-solid-infill mitigation, R72); user TYPE map (R106: visible top = Top surface, layer-1 skin = Bottom) | untagged or mis-tagged sections |
| **L4 Z-scan** | layer detection from extruding Z-changes (incl. vase-mode continuous rise) | files without layer comments |

**Honest limits (found by our own corpus):**

- A dialect that does not *spell out* a distinction cannot be split later: Kiri:Moto
  writes one `;TYPE:Perimeter` for outer AND inner walls → one editable feature, not
  two. Simplify3D and ideaMaker write **no** `;TYPE:` at all → feature menus are empty
  for those files (L3 covers the takeover case, not per-feature tuning).
- The Z-scan only sees Z **on extruding moves**. Files that set Z in a separate
  travel (`G1 Z0.4` then extrude at modal Z) get no layer marks. Most slicers emit
  combined moves on layer change, but not all.
- Marlin-volumetric files (E in mm³) are detected and warned about, not silently
  mis-measured.

## 3. Measured hit rate (R110 corpus)

`tools/r110_gcode_dialects.py` builds one structurally real file per family with
known ground truth and asserts TYPES/FS/FA/layers/marks/detection/idempotency:

| Family | Tagged features in corpus | Correct | Note |
|---|---|---|---|
| OrcaSlicer | 6 | 6/6 | incl. `gap fill` dialect fix (R94) |
| PrusaSlicer | 7 | 7/7 | |
| Cura | 7 | 7/7 | SKIN → top (layer ≥2) + bottom (layer 1) by design |
| Elegoo (Orca fork) | 6 | 6/6 | |
| Kiri:Moto | 2 | 2/2 | outer/inner not distinguishable in the dialect |
| AstroPrint (Cura fork) | 5 | 5/5 | |
| SliceBeam (Prusa fork) | 4 | 4/4 | |
| SuperSlicer | 3 | 3/3 | `Thin wall` intentionally has no own override |
| ideaMaker | 0 | — | no `;TYPE:` emitted |
| Simplify3D | 0 | — | no `;TYPE:` emitted |
| old RepRap/Marlin | 0 | — | no comments at all; layers via Z-scan |
| Marlin-volumetric | 3 | 3/3 | + volumetric flag detected |

**Corpus result: 46/46 tagged features recognized (100 %), all 13 families (.85:
+Simplify3D travel-Z, the modal-Z proof) process cleanly, all layer counts and
measured speeds exact, both S3D detection bugs fixed by the corpus itself
(`Simplify3D(R)` parentheses, `G-Code generated by` prefix).**

Translated to wild files: for the ~9 families that tag features (the overwhelming
majority of files in the field — Orca/Prusa/Cura lineage), our hit rate on
*tagged* features is effectively 100 % because we consume exactly what the slicer
itself knows. The real gap is the *untagged* families (ideaMaker, Simplify3D, old
Marlin/RepRap, some CAM), where we currently offer layer tracking + global takeover
but no per-feature menu. Rough field estimate: > 95 % of community files come from
tagging slicers; of those, the features they actually spell out are covered 1:1.

## 4. What the community does

| Approach | What it reads | Feature-level? | Verdict for us |
|---|---|---|---|
| **Slicer's own preview** (Orca/Prusa/Bambu viewer, `GCodeProcessor`) | the slicer re-parses its own output; `;TYPE:` + extrusion roles are first-class | yes — but only for its own files, inside the slicer | the gold standard we mirror at the printer; their `extrusion_role` concept is what our canonical features copy |
| **Moonraker gcode metadata** | header/footer: slicer+version, layer height, temps, filament, thumbnails, object processing (`preprocess_cancellation` → `EXCLUDE_OBJECT_DEFINE`) | **no** per-feature data — file-level only | complementary: we already show slicer/flavor; their object-processing toggle is offered by our setup wizard |
| **Klipper `[exclude_object]` + moonraker `enable_object_processing`** | object outlines, computed by moonraker at upload when the slicer did not embed them | object level, not feature level | proof that host-side geometric re-derivation works at scale — the same idea, one level coarser than ours |
| **klipper_estimator** (Annex Engineering) | full move simulation with the printer's real limits → precise time estimates; rewrites M73 | no features — but the deepest move-level parser in the field | the reference for "measure, don't believe the header"; our FS/FA measurement is the same philosophy applied to features |
| **PrettyGCode** (OctoPrint) | `;TYPE:` per slicer preset → colored toolpath | yes (display only) | same L1 layer as ours, no parameter extraction |
| **Browser previewers** (e.g. gcode-previewer) | `;TYPE:` comments + Z-based layers, chunked parsing, arcs | yes (display only) | confirms the dialect table + Z-fallback is the standard community design |
| **Academic ML** (Image2Gcode diffusion, GPAMS voxel sims, G-code attack classifiers with "G-code segmenting and labeling + ML classifier selection") | learned segment classification | research stage — trained per-dataset, no shipped tool | see roadmap: promising as L5, not needed for the tagged families |

**Bottom line:** nobody in the community ships *feature-level* detection that goes
beyond reading what the slicer wrote. The two genuinely deeper pipelines
(klipper_estimator's move simulation, moonraker's object re-derivation) stop at
time / object granularity. Our combination (dialect table + measured parameters +
geometry re-derive + per-feature overrides at runtime) is ahead of what is publicly
available for this use case.

## 5. Roadmap: pushing the hit rate higher (layered, no single bet)

1. **L3+ modal-Z tracking** (cheap, real): track Z from *travel-only* moves too, so
   files that set Z separately still get layer marks. Guard: ignore Z-hops (up-then-
   down within a few moves) — that is exactly why the current scan is conservative.
2. **Geometry classifier for untagged files** (medium): concentric/equidistant
   offsets from the layer's outer hull = walls; hatch lines with fixed angle = infill;
   crossing open spans above nothing = bridge; first/last layer surfaces. This is the
   classic "re-derive from geometry" — moonraker proves the host can afford it; we
   already run hull/offset math for the range and label generators.
3. **Movement fingerprints** (cheap additions): speed histograms per section (walls
   are slower than infill), E-per-mm (top surfaces extrude wider), short-segment
   density (gap fill), retraction-adjacent short travels (ironing). Feed them as
   *hints* with a confidence, never as silent truth.
4. **Confidence + cross-checks** (the important part): every derived feature gets a
   confidence (tagged=1.0, derived-from-geometry=0.7, fingerprint-only=0.4). The UI
   shows "detected" vs "assumed"; a per-file audit line reports how much of the
   extrusion is covered at which confidence. Tagged data always wins over derived.
5. **Slicer-config replay** (already half-built): the Prusa/Orca config block in the
   file tail carries per-feature speeds — parse it as ground truth when present
   (CFG_KEYS does this for ~20 keys today; extend to the full per-feature set).
6. **ML layer (L5, optional)**: a small classifier over move-window features
   (ΔXY, ΔE, F, curvature, neighbor context) trained on tagged files from the big
   families, used ONLY for untagged files and only with the confidence display.
   The academic work shows the features are learnable; nothing off-the-shelf ships
   this, so it would be a genuine differentiator — but it is the last 5 %, not the
   first 95 %.

## 6. Parameters worth making editable next (pre-print + live tuning)

From the census of what slicers actually emit and what the community asks for:

**Pre-Print (per file, profile-able):**

- **Line width** (global + outer wall) — in the config header, per feature in
  Orca/Prusa; currently display-only for us
- **Layer time / minimum speed / fan kick** (cooling block) — Orca/Prusa/Cura all
  emit `;TIME` per layer + fan thresholds; a "keep overhangs cool" pre-print lever
- **Extrusion multiplier per feature** (we have flow per feature for ironing only)
- **Seam position awareness** (display where the seam lands; re-slicing needed to
  move it — honest display, not fake control)
- **Travel accel** separate from print accel (Klipper supports it via per-move
  limits; klipper_estimator models exactly this)
- **Retract on layer change only / extra restart distance** — present in most
  headers, currently ignored by our takeover

**Live tuning:**

- **Per-feature flow** (not just ironing): wallouter/surface flow live — the menu
  structure exists, the multiplier plumbing exists since R73
- **Live pressure advance per feature** (Klipper supports SET_PRESSURE_ADVANCE at
  runtime; switching it on ;TYPE: boundaries like APPLY_TYPE does for speeds)
- **Fan curve override during print** (min/max clamp + bridge boost), not just the
  single % slider
- **Live input-shaper toggle** (off for outer walls, on for infill — the classic
  surface-quality trick; SET_INPUT_SHAPER is runtime-capable)
- **Z-hop height live** (we have ON/OFF live; the height is pre-print only)
- **Extrude-rate cap** (mm³/s limit — protects a hotend from infill speeds; the
  math runs in the watcher already for the plotter)

Each of these follows the existing pattern: file original shown, ON switch, live
re-apply on feature boundaries, profile-able in pre/post file profiles.

## 7. Sources

- OrcaSlicer GCodeProcessor / viewer internals (DeepWiki: g-code-generation,
  gcode-viewer-and-preview) — `;TYPE:` = extrusion role
- PrusaSlicer issue #2289 — feature types only in verbose comments
- Moonraker file-manager metadata docs + preprocess_cancellation
- Klipper Exclude_Object docs + Mainsail workflow (enable_object_processing)
- Annex-Engineering/klipper_estimator (issues #10, OrcaSlicer #2003/#2009)
- OctoPrint-PrettyGCode (plugin page + repo)
- hermes98761234/gcode-previewer (browser, ;TYPE: + Z layers + arcs)
- Academic: Image2Gcode (arXiv 2511.20636), GPAMS (ScienceDirect), G-code attack
  classification (ML segmenting/labeling), curvature-aware post-slicing optimization
  (Springer 2026)
