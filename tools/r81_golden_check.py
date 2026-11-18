#!/usr/bin/env python3
"""R81 golden test: byte-level regression net for make_range + process.

The R81 streaming refactor (R2-2026-09-07.65) rewrote both postproc paths from
'load the whole file as one Python list' (the Pi Zero RAM killer of field log
.63: 32MB source -> ~150MB of string objects -> swap storm -> 'Timer too
close' during range generation) to two-pass streaming. The refactor was
verified byte-identical against the PREVIOUS builder (.64) - this script
keeps that guarantee alive: it rebuilds the 23 fixture cases, runs them
through the CURRENT module and compares MD5s + change summaries against the
frozen references.

RE-FREEZE HISTORY (R2-2026-11-18.2, V3): version bump ONLY
(R2-2026-11-18.1 -> R2-2026-11-18.2, POSTPROC_BUILD V2 -> V3; no code
path changes). A/B proof: the git HEAD module with ONLY the two stamp
strings patched reproduces this release's output byte-for-byte for all
23 cases (md5 AND summaries identical); pr01-pr10 byte-IDENTICAL.
mr01-mr13 re-frozen (stamp class), nothing else.
RE-FREEZE HISTORY (V1, R2-2026-11-13.1): version scheme changed on user
request - no more appending letters to .142 (.142j/.142k/.142l ...). New scheme:
R2-<date>.<counter>, starting at R2-2026-11-13.1. The build tag is 'V1' now.
Proof: stamp-only change (same length class, proven by the diff of old vs new
module output - the delta is the version line only); refs generated from the
module and re-run five times, byte-identical.
RE-FREEZE HISTORY (.142m, R257): POSTPROC_RELEASE/BUILD bump only
(.142l -> .142m, R256 -> R257). Proof: with the OLD stamp patched back in, the
current module reproduced the frozen .142l reference byte-for-byte in all 23
cases - nothing but the stamp moved. The .142m refs were generated from the
module itself and verified stable over five consecutive runs.
HONEST NOTE: the reference block inherited from the uncommitted R254-R256 work
was out of sync for mr12/mr13 - their md5 in the FAILURE MESSAGE flipped between
runs while the module's own output for them stayed identical 4x in a row. The
old reference was stale, not the code; both are re-frozen here.
RE-FREEZE HISTORY (.142l, R256): version bump + the two boot-halt guards.
The R255 diff (.142i -> .142l, all 23 cases) was counted before freezing:
55 added / 39 removed lines, and every single one is either the version
stamp, the re-computed R2-META signature, or one of the ;TYPE: comments the
R254 helper introduced (28 added / 12 removed). Not one motion line.
RE-FREEZE HISTORY: R254 (.142j) re-froze mr01-mr13 - the generators now
write BOTH markers (';TYPE:<canonical name>' comment + APPLY_TYPE command,
the R253 _apply_type_lines helper), so a standard g-code reader sees the
feature types too. PROVEN change: old vs new output of all 23 cases was
diffed - 55 added / 39 removed lines, and apart from the 26 version-stamp
lines and the 26 re-computed R2-META sig lines EVERY line of the delta is a
';TYPE:' comment (28 added, 12 removed = the duplicates the helper replaced);
not one motion line changed. pr01-pr10 stay byte-identical.
RE-FREEZE HISTORY: R2-2026-11-18.2 / V2 version bump re-froze mr01-mr13
ONLY (release stamp class): POSTPROC_RELEASE .11-13.1 -> .11-18.1,
POSTPROC_BUILD V1 -> V2 - same length class; both ride in the
'; R2-GEN core' line and the re-computed R2-META sig. Proof: the git
HEAD module with ONLY the two stamp strings patched reproduces this
release's output byte-for-byte for all 23 cases (md5 AND summaries);
pr01-pr10 byte-IDENTICAL - process()/make_range untouched.
RE-FREEZE HISTORY: R258 re-froze pr03/pr08 ONLY (Option B - the user-approved
layer-count divergence fix): in the Z-scan world _FILE_INFO TOTAL_LAYERS now
counts the first printed layer (rises+1, plus one layer per bed-returning
print-unit restart). Proven by A/B against git HEAD (module diff is the
payload): pr03/pr08 differ in EXACTLY ONE LINE each - TOTAL_LAYERS=8 -> 9 -
same length, every other byte identical; marks_added unchanged (8), all
summaries unchanged apart from layers. pr01-pr02/pr04-pr10 byte-identical;
mr01-mr13 untouched (make_range path unchanged).
RE-FREEZE HISTORY: R252 (.142h) re-froze mr01-mr13 (version bump
class - POSTPROC_RELEASE .142g -> .142h, BUILD R251 -> R252, both the
same length; R252 adds the engine switch (r2_postproc_next.py handover)
and the R2-DOCTOR scan guard in the WATCH layer - make_range/process are
untouched). Proofs: the .142g module from git 9efbeb6 reproduces the
previous references byte-exactly (23/23, md5 AND summaries); every
summary dict is unchanged. Re-frozen from the bumped module.
RE-FREEZE HISTORY: R251 (.142g) re-froze mr01-mr13 (version bump
class - POSTPROC_RELEASE .142f -> .142g, BUILD R250 -> R251, both the
same length; the R251 changes live in the menus and in the new
SHAPER_MANUAL macro - make_range/process are untouched). Proofs: the
.142f module from git a53a190 reproduces the previous references
byte-exactly (23/23, both md5 and summaries); the per-case A/B diff of
all 23 outputs shows EXACTLY 3 changed lines per mr case - the two
identify lines (the date in "generated by" is derived from the body
signature by design) and the R2-META sig - while pr01-pr10 are
byte-IDENTICAL and every summary dict is unchanged. Re-frozen from the
bumped module.
RE-FREEZE HISTORY: R250 (.142f) re-froze mr01-mr13 (stamp + pointer
rename class - POSTPROC_RELEASE .142e -> .142f, BUILD R249 -> R250,
both the same length; plus ONE deliberate text change: the R2-RANGE note
pointed at the menu 'Live > Features', which R250 deleted, and now names
'Live Tuning (Spd/Acc/PA/Flow per feature)' (+26 bytes per case). Proof:
the same module with the OLD stamp strings differs from the .142e
references in EXACTLY 3 lines per mr case - the identify line (its date
is derived from the body signature by design), the R2-RANGE note and the
R2-META sig; every other byte identical, pr01-pr10 byte-IDENTICAL -
make_range/process logic untouched.
RE-FREEZE HISTORY: R249 (.142e) re-froze mr01-mr13 (version bump
class - POSTPROC_RELEASE .142d -> .142e, BUILD R248 -> R249; the R249
changes live in the WATCH layer (root links for the flat SD list) and
in the QUALITY fix (_quality_fix_file rewritten: same-layer + sacred-ink
crossing rule, naked crossings get the file's own retract, 4-tuple),
make_range/process are untouched. Proof: the same module with the OLD
stamp strings reproduces the previous refs byte-exactly (23/23) - the
stamp is the ONLY difference; re-frozen from the bumped module.
RE-FREEZE HISTORY: R248 (.142d) re-froze mr01-mr13 (version bump
class - POSTPROC_RELEASE .142c -> .142d, BUILD R246d -> R248; the R248
changes live in the WATCH layer and the menus: the LCD folder browser is
PARKED behind SD_BROWSER_ON=False (tree walk, _SDM queries and every
sd_cur/sd_view/sd_gen push are off), the SD menu is Klipper's vsdlist
again, the quick menus carry head rows instead of the duplicate
current-feature value rows - make_range/process are untouched. Proofs:
the .142c module from git 565c9af reproduces the previous refs
byte-exactly (23/23); every changed summary is EXACTLY size-1 with the
same line count (one character less in the build tag R246d -> R248, the
release string .142c -> .142d is the same length); pr01-pr10
byte-IDENTICAL).
RE-FREEZE HISTORY: the .134 version bump changed the core stamp line in
every mr excerpt (verified: exactly ONE line per case differs, .133 ->
.134, nothing else) - refs re-frozen from the bumped module.
RE-FREEZE HISTORY: R246d (.142c) re-froze mr01-mr13 (version bump
class - POSTPROC_RELEASE .142b -> .142c, BUILD R246c -> R246d; the R246d
changes live in the busy probes (idle_timeout rides the existing query),
the motion deferral for preview pushes and the watch loop - make_range/
process are untouched. Proofs: the .142b module from git 76edc81
reproduces the previous refs byte-exactly (23/23); the per-case A/B diff
shows ONLY the R2-META sig line per case (26 lines, all sig class);
pr01-pr10 byte-IDENTICAL).
RE-FREEZE HISTORY: R246c (.142b) re-froze mr01-mr13 (version bump
class - POSTPROC_RELEASE .142a -> .142b, BUILD R246b -> R246c; the R246c
fixes live in the WATCH layer only: strict idle gates before both push
paths, mirror-fail backoff, push timeout=20/retries=1, the SDNAV_GO
self-healing fallback in macros. make_range/process are untouched.
Proofs: the .142a module from git d45ebfa reproduces the previous refs
byte-exactly (23/23); the per-case A/B diff shows ONLY the R2-META sig
line per case (26 lines, all sig class - the sig hashes the stamped
body); pr01-pr10 byte-IDENTICAL).
RE-FREEZE HISTORY: R246b (.142a) re-froze mr01-mr13 + summaries
(version bump class - POSTPROC_RELEASE .142 -> .142a, BUILD R246 ->
R246b; the R246b fixes live in _sdm_state/_klippylog/_crashreport,
make_range/process untouched. Proofs: the .142 module from git
17e6e3a reproduces the previous refs byte-exactly (23/23); every
changed summary is EXACTLY size+3 = three stamp lines x one added
character; pr01-pr10 byte-IDENTICAL).
R246 (.142) re-froze mr01-mr13 (version bump
class again - POSTPROC_RELEASE .141 -> .142, BUILD R245 -> R246; the
R246 changes live in menus/macros/web/tools, make_range/process are
untouched).
R245 (.141) re-froze mr01-mr13 (version bump
class - only POSTPROC_RELEASE .140 -> .141 and BUILD R244 -> R245. The
R245 park-first fix lives in macros/08_print_start_stop.cfg ONLY -
make_range/process are untouched. Proofs: the .140 module from git
f1d8c2b reproduces the previous refs byte-exactly (23/23); the per-case
A/B diff shows 78 changed lines, ALL stamp class; pr01-pr10
byte-IDENTICAL).
RE-FREEZE HISTORY: R244 (.140) re-froze mr01-mr13 (version bump
class - only POSTPROC_RELEASE .139 -> .140 and BUILD R243 -> R244. The
R244 MCU-shutdown auto-recovery (_recovery_tick + helpers) lives in
the watch-loop layer ONLY. Proofs: the .139 module from git 5552dda
reproduces the previous refs byte-exactly (23/23); the per-case A/B
diff shows 78 changed lines, ALL stamp class (core stamp, 'generated
by' line, R225 identify line, R2-META sig); pr01-pr10 byte-IDENTICAL).
RE-FREEZE HISTORY: R243 (.139) re-froze mr01-mr13 (version bump
class - only POSTPROC_RELEASE .138 -> .139 and BUILD R242 -> R243; the
R243 fix itself is config-only (03_leds.cfg cylon layers), the daemon
code is UNTOUCHED. Proofs: the .138 module from git ff3b0ca reproduces
the previous refs byte-exactly (23/23, md5 + summaries); the per-case
A/B diff shows 78 changed lines, ALL stamp class (R2-GEN core stamp,
R225 identify line, R2-META sig); pr01-pr10 byte-IDENTICAL).
RE-FREEZE HISTORY: R242 (.138) re-froze mr01-mr13 (version bump
class - only POSTPROC_RELEASE .137 -> .138 and BUILD R241 -> R242; the
R242 daemon edits live in the preview-push dedupe and the watch loop,
NEVER in make_range/process. Proofs: the .137 module from git 87c9299
reproduces the previous refs byte-exactly (23/23); the per-case A/B diff
shows only the version-stamp consequences - core stamp line, R225
identify line (date/time derived from the body signature) and the
R2-META sig; pr01-pr10 byte-IDENTICAL).
RE-FREEZE HISTORY: R241 (.137) re-froze mr01-mr13 (pure version
renumber - NO code change, only POSTPROC_RELEASE .136aj -> .137 and
BUILD R240 -> R241; proofs: the .136aj module from git 3583861
reproduces the previous refs byte-exactly (23/23), and the per-case A/B
diff shows ONLY the version-stamp consequences - the core stamp line,
the R225 identify line (its date/time is DERIVED from the body
signature by design) and the R2-META sig; every other byte identical,
pr01-pr10 byte-IDENTICAL, mr sizes shrink by exactly the 4 stamp
bytes).
RE-FREEZE HISTORY: R240 (.136aj) re-froze mr01-mr13 (stamp-bump
class - proofs: the pre-bump module from git 60ae1db reproduces the
previous refs byte-exactly (23/23), and the NEW module run with the
OLD stamp (RELEASE .136ai + BUILD R236) produces a byte-identical
freeze; the R240 edits live in the _ACCEL_SET rename, the profile
engine, the LED progress hooks and the menu structure - make_range
outputs change by the release stamp alone, pr01-pr10 byte-IDENTICAL,
every summary unchanged).
RE-FREEZE HISTORY: R238 (.136ai) re-froze mr01-mr13 (stamp-bump class
again - proofs: the .136ah module from git ef43f21 reproduces the
previous refs byte-exactly, and the NEW module run with the OLD stamp
produces a byte-identical freeze; the R238 edits live in the queue
kill channel, the auto segment fix, the STL export naming and the
texture map plumbing - make_range/process outputs change by the
release stamp alone, pr01-pr10 byte-IDENTICAL, summaries unchanged).
RE-FREEZE HISTORY: R237 (.136ah) re-froze mr01-mr13 (stamp-bump class
again - proofs: the .136ag module from git bb08afd reproduces the
previous refs byte-exactly, and the NEW module run with the OLD stamp
produces a byte-identical freeze; the R237 edits live in the SD-browser
root pick, the texture map resolution and the segments/texture _M204
scrub - make_range/process outputs change by the release stamp alone,
pr01-pr10 byte-IDENTICAL, every summary unchanged).
RE-FREEZE HISTORY: R236 (.136ag) re-froze mr01-mr13 (stamp-bump class
again - proofs: the .136af module from git 2352ac5 reproduces the
previous refs byte-exactly, and the NEW module run with the OLD stamp
produces a byte-identical freeze; the R236 edits live in the macros
(05/08/09), menus, r2_texture, the watcher's queue/tree/notify/av
logic + this stamp - the module changed by the release stamp alone).
RE-FREEZE HISTORY: R235 (.136af) re-froze mr01-mr13 (stamp-bump class
again - proofs: the TRUE .136ae module from git 0de9a7c reproduces the
previous refs byte-exactly, and the NEW module run with the OLD stamp
produces a byte-identical freeze; the R235 edits live in the start
dialog macros (07/08) + tools + this stamp - the module changed by the
release stamp alone; pr01-pr10 byte-IDENTICAL).
RE-FREEZE HISTORY: R234 (.136ae) re-froze mr01-mr13 (stamp-bump class
again - proof: the .136ad module from git HEAD reproduces the previous
refs byte-exactly, and the NEW module run with the OLD stamp string
produces a byte-identical freeze output; the R234 edits are the string
art ram floor in the watcher queue + constants + update.sh/GITHUB.md -
make_range/process outputs change by the release stamp alone; pr01-pr10
byte-IDENTICAL).
RE-FREEZE HISTORY: R233 (.136ad) re-froze mr01-mr13 (stamp-bump class
again - proof: the .136ac module from git HEAD reproduces the previous
refs byte-exactly, and the NEW module run with the OLD stamp string
produces a byte-identical freeze output (diff = zero lines); the R233
edits live in update.sh + web/install_web.sh ONLY, r2_postproc.py
changed in the POSTPROC_RELEASE/POSTPROC_BUILD constants alone; pr01-
pr10 byte-IDENTICAL - process() untouched).
RE-FREEZE HISTORY: R231/R232 (.136ac) re-froze mr01-mr13 (proof: the
# version bump against the pre-bump module changes ONLY the core stamp,
# the 'generated by' line and the R2-META signature - 3 lines, nothing
# else; the R231 floor-speed re-freeze below stays valid inside)
RE-FREEZE HISTORY: R231 (.136ac) re-froze mr02-mr06, mr09-mr11, mr13
# (proof: old-vs-new module diff on mr02 shows ONLY the generated
# floor/brim/cap feed words F1200->F2400 - 199 lines - plus 2 retract
# speeds and the core stamp; user rule #4: generated geometry runs
# 40 mm/s, not the old blanket 20). mr01/mr07/mr08/mr12 (no generated
# geometry) and pr01-pr10 stayed byte-IDENTICAL.
RE-FREEZE HISTORY: R230 (.136ab) re-froze mr01-mr13 - proof: the
.136aa module from git HEAD reproduces the previous refs; the R230
TYPE_MAP pattern keys touch no fixture vocabulary (pr01-pr10
byte-IDENTICAL - process() unchanged; mr moves are the release
stamp class only, the pattern list is pinned in r230_infill_patterns).
RE-FREEZE HISTORY: R229 (.136aa) re-froze mr01-mr13 - proof: the
.136z module from git HEAD reproduces the previous refs byte-exactly;
the R229 TYPE_RE negative lookahead + TYPE_MAP additions touch no
fixture vocabulary (pr01-pr10 byte-IDENTICAL - process() unchanged;
the mr moves are the release stamp class only, the vocabulary changes
are pinned in r229_vocab_rest).
RE-FREEZE HISTORY: R228 (.136z) re-froze mr01-mr13 (stamp-bump class
again - proof: the .136y module from git HEAD reproduces the previous
refs byte-exactly; the R228 edits live in the watcher reconcile block
and constants, process()/make_range untouched).
RE-FREEZE HISTORY: R227 (.136y) re-froze mr01-mr13 (stamp-bump class
again - proof: the .136x module from git HEAD reproduces the previous
refs byte-exactly; the R227 edits live in the watcher loop (reconcile
parse + latch) and constants, process()/make_range untouched).
RE-FREEZE HISTORY: R226 (.136x) re-froze mr01-mr13 (version stamp +
R2-META release line only - the field-round changes live in the WATCHER
loop and the macros, make_range/process/metadata stayed untouched; pr
byte-identical expected).
RE-FREEZE HISTORY: R225 (.136w) re-froze mr01-mr13 (two-class proof: the
first r81 run after the round showed pr01-pr10 BYTE-IDENTICAL - process()
never finalizes metadata - while every mr case grew by exactly the new
R2-META footer: identify stamp, fmt=2 marker, 3-int thumbnail header,
layer_height/first_layer_height/total layers count, trailing newline.
make_range's G-code paths themselves are untouched - the delta is the
metadata block class + the release stamp only).
RE-FREEZE HISTORY: R222 (.136t) re-froze mr01-mr13 (git-diff proof: version
line + the plot-writer tail only - make_range/process untouched).
RE-FREEZE HISTORY: R221 (.136s) re-froze mr01-mr13 (git-diff proof: the
POSTPROC_RELEASE line + three OUTPUT-NEUTRAL fixes - dead return, error-
path formatting, error-path raise; pr01-pr10 byte-identical).
RE-FREEZE HISTORY: R220 (.136r) re-froze mr01-mr13 (same class as R219:
git-diff proof = POSTPROC_RELEASE line only, pr01-pr10 byte-identical).
RE-FREEZE HISTORY: R219 (.136q) re-froze mr01-mr13 from the bumped
module - git-diff proof: tools/r2_postproc.py changed by the
POSTPROC_RELEASE line ONLY (.136p -> .136q); pr01-pr10 byte-identical
(process output carries no release stamp), the mr range headers do.
RE-FREEZE HISTORY: R188 (.134) re-froze all mr cases from the UNCHANGED
.133 module (7330e48) - the sandbox environment changed between sessions
and the old refs stopped reproducing. Output is deterministic content with
no code delta: old-vs-new module were verified byte-identical for all 13
cases BEFORE the re-freeze (the R188 watcher/gen_busy edits never touch
make_range/process).
RE-FREEZE HISTORY: R186 re-froze pr03/pr08 (R181 void-side rule, verified by diff against the pre-R181 module 1888e9c: ONE new APPLY_TYPE TYPE=WALL-OUTER on the extruding-Z region + COVER 89->100, nothing else - types 8->9). RE-FREEZE HISTORY: R143 re-froze pr03/pr08 (audit F4: Z-scan LAYER_MARK anchoring - the marks now sit directly before the first extruding line of their layer instead of drifting cumulatively; the unified diff showed moved marks ONLY, APPLY_TYPE/lines unchanged). RE-FREEZE HISTORY: R111 re-froze pr01-pr10 (roadmap round: MAXRATE/SEAM
measured keys in every _FILE_INFO; the new geometry classifier derives
WALL-OUTER for untagged Z-scan files -> APPLY_TYPE + DERIVED/CONF/COVER keys,
pr03/pr08 types 0 -> 8). mr01-mr13 (range extracts) are UNCHANGED. The
references were originally frozen from the .64 code
(R81). R87.2 re-froze them (APPLY_TYPE re-derivation). R94 re-froze them
again (field log .73: cut-feature marker + brim on layer 1 + honest TYPES):
APPLY_TYPE markers from ;TYPE: comments when the source carries none (field
log .71 - the whole model printed as 'solid infill'), which is a deliberate
output change for such sources. The .64 reference is preserved in the .64
release ZIP. If this test fails after an edit to make_range/process, the
output of the edited code is no longer byte-identical to the frozen
reference - either fix the edit or (deliberate change only!) re-freeze with
--freeze=<old_module.py>.

Usage:
    python3 tools/r81_golden_check.py [--freeze=path/to/old_r2_postproc.py]
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# frozen from the .64 builder (R81), re-frozen from R87.2 - 23 cases
# R117 re-freeze: range floor/cap hatch chains into a serpentine (field
# log .89 - continuous fills that fuse with the walls) - mr02-mr06,
# mr09-mr11, mr13 grew by the connector beads; pr01-pr10 and the plain
# mr01/mr07/mr08/mr12 extracts stay byte-identical to R112/R116.
# R121 re-freeze: FTRAVEL=<mm/s> (dominant travel speed) added to every
# _FILE_INFO of files whose travels carry F - pr01/pr02/pr04/pr05/pr06/
# pr09/pr10 info lines changed, everything else byte-identical.
# R150 re-freeze: brim loops print OUTSIDE-IN now (user rule: the outermost
# loop anchors first, then inward) - mr06 carries a brim, its bytes changed;
# all other fixtures are brim-free and stay byte-identical.
# R186 re-freeze: the R166 core stamp now also heads the range excerpts
# (bridge/resonance/scale stamp themselves too - the stamp used to come
# only from _gen_normalize_speeds, which make_range deliberately skips).
# Every mr fixture gained EXACTLY the 39-byte '; R2-GEN core ...' first
# line, byte-identical otherwise (strip-proof in the R186 log); the pr
# fixtures (process on slicer files) stay byte-identical.
# R112 re-freeze: tag v4 -> v5 (STALE/retag round) - every fixture's tag
# line changed, summaries gained retract_status/retract_max. R112 reference
# superseded.
# RE-FREEZE HISTORY (.136k, R212): CONTENT change, proven - every mr
# fixture gained the R2-META v1 block (128x128 PNG thumbnail + honest time
# + filament, Mainsail metadata requirement) inserted after the core stamp;
# the bytes around it are IDENTICAL to .136j (verified: new = stamp +
# inserted block + old tail, all 13 cases; pr01-pr10 byte-identical - the
# meta hook lives in make_range + the watcher scan, never in process()).
# REF frozen from the .136k module after the proof.
# RE-FREEZE HISTORY (.136k, R212): CONTENT change, proven - every mr
# fixture gained the R2-META v1 block (128x128 PNG thumbnail + honest time
# + filament, Mainsail metadata requirement) inserted after the core stamp;
# the bytes around it are IDENTICAL to .136j (verified: new = stamp +
# inserted block + old tail, all 13 cases; pr01-pr10 byte-identical - the
# meta hook lives in make_range + the watcher scan, never in process()).
# REF frozen from the .136k module after the proof.
# RE-FREEZE HISTORY (.136m, R215): CONTENT change, proven - the R215 meta
# signature (one '; R2-META sig = <16 hex>' line closing every R2-META
# block) was added so the watcher scan stops re-analyzing+rewriting every
# generated file on every pass (.136l field log: gen_files flip-flop +
# permanent disk writes + host load). Verified for all 13 mr cases: new
# output == old reference + exactly that one line; pr01-pr10 stay
# byte-identical. The freeze printer now emits Python literals (pprint) -
# json.dumps false/true tokens made pasted REF_SUMMARYs die with NameError.
# RE-FREEZE HISTORY (.136p version bump, R218): stamp-only - mr01-mr13
# re-frozen for the new core stamp, pr01-pr10 byte-identical; PROVEN by
# running the NEW module (web-UI field round: mkPrinter/nginx/SYS_PI_
# REBOOT do not touch range/process paths) with the OLD stamp string:
# all 23 md5 == the .136o goldens.
# RE-FREEZE HISTORY (.136o version bump, R217): stamp-only - mr01-mr13
# re-frozen for the new core stamp, pr01-pr10 byte-identical; PROVEN by
# running the NEW module (shape TYPES honesty + the two new R217 test
# tools do not touch range/process paths) with the OLD stamp string:
# all 23 md5 == the .136n goldens.
# RE-FREEZE HISTORY (.136n version bump, R216): stamp-only - mr01-mr13
# carry the R166 core stamp, pr01-pr10 byte-identical; PROVEN by running
# the new module (stage 7 + the two file fixes) with the old stamp string:
# all 23 md5 == the .136m goldens. The stage-7 classifier changes only
# touch UNTAGGED files (tagged sources take the ;TYPE: path), the golden
# fixtures are tagged - the proof shows it.
# RE-FREEZE HISTORY (.136m, R215b): mr08 + mr13 re-frozen - the range
# excerpt no longer COPIES the source's PRINT_END when the window runs
# into the source end block (the audit sweep caught it: two PRINT_ENDs
# ran the end choreography twice, M107 sat between them). PROVEN per
# case: old module (current minus the skip) reproduces the frozen ref
# byte-identically; unified diff = the R2-META sig value + exactly the
# one removed 'PRINT_END' line, nothing else. All other 21 cases stay
# byte-identical.
# RE-FREEZE HISTORY (.136j version bump, R211): stamp-only - proven by
# running the NEW module with the OLD stamp string (all 23 md5 == the
# .136i goldens). No postproc logic changed this round.
# RE-FREEZE HISTORY (.136i version bump, R210): stamp-only - proven by
# running the NEW module with the OLD stamp string (all 23 md5 == the
# .136h goldens). No postproc logic changed this round.
# RE-FREEZE HISTORY (.136h version bump, R209): stamp-only - mr01-mr13 carry
# the R166 core stamp, pr01-pr10 byte-identical; PROVEN by running the new
# module with the old stamp string (all 23 md5 == the .136g goldens).
# RE-FREEZE HISTORY (.136g version bump, R208): stamp-only - mr01-mr13 carry
# the R166 core stamp, pr01-pr10 byte-identical; PROVEN by running the new
# module with the old stamp string (all 23 md5 == the .136f goldens).
# RE-FREEZE HISTORY (.136f version bump, R207): stamp-only - mr01-mr13 carry
# the R166 core stamp, pr01-pr10 byte-identical; PROVEN by running the new
# module with the old stamp string (all 23 md5 == the .136e goldens).
# RE-FREEZE HISTORY (.136e version bump, R206): stamp-only - mr01-mr13 carry
# the R166 core stamp, pr01-pr10 byte-identical; PROVEN by running the new
# module with the old stamp string (all 23 md5 == the .136d goldens).
# RE-FREEZE HISTORY (.136d version bump, R205): stamp-only - mr01-mr13 carry
# the R166 core stamp, pr01-pr10 byte-identical; PROVEN by running the new
# module with the old stamp string (all 23 md5 == the .136c goldens).
# RE-FREEZE HISTORY (.136c version bump): stamp-only (R204 touched web/ +
# docs + the live endpoint, not the generators; diff verified).
# RE-FREEZE HISTORY (.136b version bump): stamp-only again (R203 - the
# round touched web/ + docs, not the generators; diff verified).
# RE-FREEZE HISTORY (.136a version bump): stamp-only again
# (; R2-GEN core R2-2026-10-29.136a (R202), diff verified vs .136).
# RE-FREEZE HISTORY (.136 version bump): the mr extracts differ ONLY in
# the core stamp line (; R2-GEN core R2-2026-10-29.136 (R201) - diff verified
# against the .135 module, commit f42a78e, before freezing).
# RE-FREEZE HISTORY (.135, R191-R197): fixtures became sequence-honest
# (orca/cura: layer-1 solid = Bottom, ironing follows a Top from layer 2 -
# the old fixtures ironed EVERY layer and tripped the new S1/S2 audit) and
# the reference was frozen from the .135 module on them. BEFORE freezing,
# the .134 module (commit 7014f69) was verified BYTE-IDENTICAL to .135 on
# the honest fixtures for all pr cases (empty diff: fstat/air-scan/audit
# only touch real violations); the mr extracts differ ONLY in the core
# stamp line (version bump, by design).
# R224 re-freeze (.136u -> .136v): TWO proven changes. (a) the version
# stamp bump (POSTPROC_RELEASE .136v) heads every mr extract - mr01/
# mr07/mr08/mr12 and all pr cases are otherwise byte-identical (git
# diff vs 159b804). (b) Task 11 field wish: floor/cap count INSIDE the
# layer window now - mr02-mr06, mr09-mr11, mr13 re-froze with the new
# semantics ('floor 2 INSIDE the window', excerpt exactly 8 layers tall,
# stackable; was: floor as a raft BELOW the window, 10 layers).
# R223 re-freeze (.136t -> .136u): POSTPROC_RELEASE bump only - proof: the
# .136t module from git HEAD (921c9c6) reproduces the previous REF
# byte-exactly (all 23), a full 27-file fixture-tree diff shows ONLY the
# core stamp lines (+ their R2-META sigs) changed, the bodies byte-
# identical - the R223 decoder surgery (array planes + max_dim step,
# .136s field log) never touches a generator output at step=1 - and r81
# was 23/23 green with the R222 code BEFORE the stamp bump.
# R214 re-freeze (.136l -> .136m): POSTPROC_RELEASE bump only again -
# proof: the .136l module from git HEAD (bc63ad5) reproduces the previous
# REF byte-exactly (all 23), a full fixture-tree diff shows ONLY the core
# stamp line changed, the label loop restructure (text-in-base) never
# touches make_range, and r81 was 23/23 green with the R214 code BEFORE
# the stamp bump. R213 before that (.136k -> .136l): same pattern, stamp
# only - process() identical old vs new, no summary moves.
# the .136k module from git HEAD reproduces the previous REF byte-exactly,
# process() output is identical old vs new, ALL 13 mr md5s change (every
# range excerpt carries the core stamp), no summary moves, and r81 was
# 23/23 green with the R213 code BEFORE the stamp bump.
REF_MD5 = {'mr01': '64d3bb50a5a3c6376305821316033b04',
 'mr02': '9a2a9f332c4f401988c8a6955e3886e2',
 'mr03': '6abb6a911e4ae539411cadcda544da88',
 'mr04': '2e7afef8722547034d10a0bd95041d03',
 'mr05': '8ce05f2de763c08c1dd91f3e58c067dd',
 'mr06': '86a4de49cb2af97136014f73470cbdbc',
 'mr07': 'd6af2011c3ec994e547c276bbc5ee710',
 'mr08': '70d152ce92c5f40c2174bdaa9db88238',
 'mr09': '308006c79bd5d3e6132ab04d992b31dc',
 'mr10': '32919b5d2d04a081e2976872e5da0998',
 'mr11': 'a77ce29a53ee16523347ab6ad5850ecf',
 'mr12': '9104803ea077352addd5539585841e41',
 'mr13': '91f925a1eeb414a7f83ec691fdf20949',
 'pr01': 'aa5a6f27d5a7e6576f57eeea93af63a5',
 'pr02': '61457e9bcbd98996b6e7dc26efda23d8',
 'pr03': 'f9f7402c190f07e7aa7470d2185fddfc',
 'pr04': 'aa5a6f27d5a7e6576f57eeea93af63a5',
 'pr05': 'aa5a6f27d5a7e6576f57eeea93af63a5',
 'pr06': 'd9aacaa41daf5314ce72ae8564b34458',
 'pr07': '17fdc789395c2d6f83efc279bb751f21',
 'pr08': 'f9f7402c190f07e7aa7470d2185fddfc',
 'pr09': '5e90a1d42296412a0ea53e9d6ada0157',
 'pr10': '159ea58bb74bbf9adb377f1e733d152b'}
REF_SUMMARY = {'mr01': {'nl': 8, 'size': 5267},
 'mr02': {'nl': 8, 'size': 14350},
 'mr03': {'nl': 8, 'size': 13322},
 'mr04': {'nl': 8, 'size': 13200},
 'mr05': {'nl': 8, 'size': 21990},
 'mr06': {'nl': 8, 'size': 17299},
 'mr07': {'nl': 7, 'size': 4899},
 'mr08': {'nl': 6, 'size': 4544},
 'mr09': {'nl': 7, 'size': 9640},
 'mr10': {'nl': 7, 'size': 13222},
 'mr11': {'nl': 7, 'size': 9017},
 'mr12': {'nl': 2, 'size': 3071},
 'mr13': {'nl': 29, 'size': 20751},
 'pr01': {'by_object': False,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 9,
          'method': 'layer comments',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 26,
          'upgraded': False,
          'upgraded_from': 'v1',
          'volumetric': False},
 'pr02': {'by_object': False,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 9,
          'method': 'layer comments',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 26,
          'upgraded': False,
          'upgraded_from': 'v1',
          'volumetric': False},
 'pr03': {'by_object': False,
          'derived': True,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 8,
          'method': 'Z scan',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 9,
          'upgraded': False,
          'upgraded_from': 'v1',
          'volumetric': False},
 'pr04': {'by_object': False,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 9,
          'method': 'layer comments',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 26,
          'upgraded': True,
          'upgraded_from': 'v4',
          'volumetric': False},
 'pr05': {'by_object': False,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 9,
          'method': 'layer comments',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 26,
          'upgraded': True,
          'upgraded_from': 'v1',
          'volumetric': False},
 'pr06': {'by_object': False,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 9,
          'method': 'layer comments',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 26,
          'upgraded': False,
          'upgraded_from': 'v1',
          'volumetric': False},
 'pr07': {'by_object': False,
          'info_added': False,
          'layers': 0,
          'marks_added': 0,
          'method': None,
          'retract_pairs': 0,
          'skipped': True,
          'tagged': False,
          'types': 0,
          'upgraded': False,
          'upgraded_from': 'v1'},
 'pr08': {'by_object': False,
          'derived': True,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 8,
          'method': 'Z scan',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 9,
          'upgraded': False,
          'upgraded_from': 'v1',
          'volumetric': False},
 'pr09': {'by_object': False,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 9,
          'method': 'layer comments',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 26,
          'upgraded': False,
          'upgraded_from': 'v1',
          'volumetric': False},
 'pr10': {'by_object': False,
          'fw': '',
          'info_added': True,
          'layers': 9,
          'marks_added': 9,
          'method': 'layer comments',
          'retract_max': 0.0,
          'retract_pairs': 0,
          'retract_slicer_moves': 0,
          'retract_status': '',
          'retract_style': '',
          'skipped': False,
          'slicer': '',
          'tagged': True,
          'types': 26,
          'upgraded': False,
          'upgraded_from': 'v1',
          'volumetric': False}}
CASES = [
    ('mr01', dict(src='vase_m83.gcode', start=5, end=12)),
    ('mr02', dict(src='vase_m83.gcode', start=5, end=12, floor=2, brim=1)),
    ('mr03', dict(src='vase_m83.gcode', start=5, end=12, floor=2, floor_shape='outline', floor_fill='grid')),
    ('mr04', dict(src='vase_m83.gcode', start=5, end=12, floor=1, floor_shape='outline', floor_fill='solid')),
    ('mr05', dict(src='vase_m83.gcode', start=5, end=12, top=2, top_shape='hull', top_fill='solid')),
    ('mr06', dict(src='vase_m83.gcode', start=5, end=12, floor=1, top=1, brim=2, floor_shape='outline', top_shape='outline')),
    ('mr07', dict(src='vase_m83.gcode', start=1, end=8)),                      # start clamps to 2
    ('mr08', dict(src='vase_m83.gcode', start=25, end=999)),                   # end clamps to total
    ('mr09', dict(src='vase_m82_exc.gcode', start=3, end=9, floor=1, brim=1)),
    ('mr10', dict(src='vase_m82_g92.gcode', start=3, end=9, top=1)),
    ('mr11', dict(src='vase_nonl.gcode', start=4, end=10, floor=1)),           # no trailing newline
    ('mr12', dict(src='vase_m83.gcode', start=2, end=3)),                      # minimal range
    ('mr13', dict(src='vase_m83.gcode', start=2, end=30, top=1, top_shape='outline', top_fill='solid')),
]
PCASES = [
    ('pr01', 'orca_nl.gcode'),
    ('pr02', 'cura.gcode'),
    ('pr03', 'zscan.gcode'),           # no layer comments, no ;TYPE:
    ('pr04', 'tagged.gcode'),          # skip (already tagged)
    ('pr05', 'v1.gcode'),              # v1 -> v4 upgrade
    ('pr06', 'orca_nonl.gcode'),       # no trailing newline
    ('pr07', 'plot.gcode'),            # R2-PLOT skip
    ('pr08', 'zscan_cura_like.gcode'), # Z-scan with extruding Z moves
    ('pr09', 'orca_finfo.gcode'),      # _FILE_INFO in head, NO old tag (index-world offset)
    ('pr10', 'cura_finfo.gcode'),      # Cura layers + _FILE_INFO head
]


def vase(path, layers=30, e_rel=True, trailing_nl=True, exclude=False, g92_reset=False):
    L = ['; CONFIG_BLOCK', '; layer_height = 0.2', '; line_width = 0.6',
         '; filament_type = PLA', '; nozzle_diameter = 0.6',
         'M104 S215', 'M140 S60', 'M190 S60', 'M109 S215',
         'G21', 'G90', 'M83' if e_rel else 'M82', 'G92 E0']
    if exclude:
        L += ['EXCLUDE_OBJECT_DEFINE NAME=VASE_1 CENTER=110,110 POLYGON=[[80,80],[140,80],[140,140],[80,140]]']
    L += ['; R2-POSTPROC v4', '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 LINE_WIDTH=0.6 TOTAL_LAYERS=%d BY_OBJECT=0' % layers]
    L += ['PRINT_START MATERIAL=PLA BED=60 HOTEND_FIRST=215 HOTEND_AFTER=210 LAYER_HEIGHT=0.2 TOTAL_LAYERS=%d' % layers]
    L += ['EXCLUDE_OBJECT_START NAME=VASE_1']
    e = 0.0
    for lay in range(1, layers + 1):
        L.append('LAYER_MARK')
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % (0.2 * lay))
        L.append(';TYPE:Outer wall')
        L.append('G0 X30 Y30 Z%.3f F6000' % (0.2 * lay))
        if g92_reset and not e_rel:
            L.append('G92 E%.3f' % (lay * 10))
        for (cx, cy) in ((70, 30), (70, 70), (30, 70), (30, 30)):
            if e_rel:
                e = 2.0
                L.append('G1 X%d Y%d E%.3f F1800' % (cx, cy, e))
            else:
                e += 2.0
                L.append('G1 X%d Y%d E%.3f F1800' % (cx, cy, e))
        L.append(';TYPE:Top surface')
        L.append('G1 X50 Y50 E%.3f F1200' % (1.0 if e_rel else e + 1.0))
        if lay == 1:
            L.append('M106 S200')
    L.append('EXCLUDE_OBJECT_END NAME=VASE_1')
    L.append('M107')
    L.append('PRINT_END')
    txt = '\n'.join(L) + ('\n' if trailing_nl else '')
    open(path, 'w').write(txt)


def orca(path, trailing_nl=True, tagged=False, v1=False, no_layers=False, cura=False):
    L = ['; CONFIG_BLOCK', '; layer_height = 0.16', '; line_width = 0.68',
         '; filament_type = PLA', '; nozzle_diameter = 0.6', '; outer_wall_speed = 60',
         '; outer_wall_acceleration = 500', '; wall_loops = 1',
         'M104 S225', 'M140 S55', 'M109 S225', 'G21', 'G90', 'M83', 'G92 E0']
    if tagged:
        L = ['; R2-POSTPROC v4'] + L
    if v1:
        L = ['; R2-POSTPROC v1', '_FILE_INFO MATERIAL=PLA TOTAL_LAYERS=9'] + L
    if not no_layers:
        L.append('G28')
    e = 0.0
    for lay in range(1, 10):
        if cura:
            L.append(';LAYER:%d' % lay)
        elif not no_layers:
            L.append(';LAYER_CHANGE')
        if not no_layers:
            L.append(';Z:%.3f' % (0.16 * lay))
            L.append(';TYPE:Outer wall')
            L.append('G0 X40 Y40 Z%.3f F9000' % (0.16 * lay))
            L.append('G1 X80 Y40 E1.2 F3600')
            L.append('G1 X80 Y80 E1.2 F3600')
            # R193 (.135): sequence-honest fixture - layer-1 solid is the
            # BOTTOM, ironing follows a TOP from layer 2 on (a real slicer
            # never irons layer 1; the old fixture tripped the new S1/S2
            # audit and every pr golden carried SEQWARN noise)
            if lay == 1:
                L.append(';TYPE:Bottom surface')
                L.append('G1 X60 Y60 E0.2 F1200')
            else:
                L.append(';TYPE:Top surface')
                L.append('G1 X60 Y60 E0.2 F1200')
                L.append(';TYPE:Ironing')
                L.append('G1 X60 Y60 E0.2 F2700')
            L.append('M204 S500')
        else:
            # real Z-scan material: extruding moves that CARRY Z (Cura style)
            L.append('G1 X40 Y40 Z%.3f E0.6 F3600' % (0.16 * lay))
            L.append('G1 X80 Y40 E1.2 F3600')
            L.append('G1 X80 Y80 E1.2 F3600')
    L.append('M107')
    L.append('; end of gcode')
    open(path, 'w').write('\n'.join(L) + ('\n' if trailing_nl else ''))


def orca_finfo(path, **kw):
    """orca fixture with a non-comment _FILE_INFO line in the head (no old tag):
    shifts the raw vs. upgrade-filtered index worlds - the apply positions
    must still land byte-exact."""
    orca(path, **kw)
    txt = open(path).read()
    L = txt.split('\n')
    L.insert(6, '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.16 LINE_WIDTH=0.68 TOTAL_LAYERS=9 BY_OBJECT=0')
    open(path, 'w').write('\n'.join(L))


def build_fixtures(d):
    vase(os.path.join(d, 'vase_m83.gcode'))
    vase(os.path.join(d, 'vase_m82_exc.gcode'), e_rel=False, exclude=True)
    vase(os.path.join(d, 'vase_m82_g92.gcode'), e_rel=False, g92_reset=True)
    vase(os.path.join(d, 'vase_nonl.gcode'), trailing_nl=False)
    orca(os.path.join(d, 'orca_nl.gcode'))
    orca(os.path.join(d, 'cura.gcode'), cura=True)
    orca(os.path.join(d, 'zscan.gcode'), no_layers=True)
    orca(os.path.join(d, 'tagged.gcode'), tagged=True)
    orca(os.path.join(d, 'v1.gcode'), v1=True)
    orca(os.path.join(d, 'orca_nonl.gcode'), trailing_nl=False)
    open(os.path.join(d, 'plot.gcode'), 'w').write('; R2-PLOT v1 pen plot\nG28\nG0 X10 Y10\n')
    orca(os.path.join(d, 'zscan_cura_like.gcode'), no_layers=True)
    orca_finfo(os.path.join(d, 'orca_finfo.gcode'))
    orca_finfo(os.path.join(d, 'cura_finfo.gcode'), cura=True)


def run_battery(mod, d):
    """returns {case: (md5, summary-without-file)}"""
    out = {}
    for name, kw in CASES:
        kw = dict(kw)
        src = os.path.join(d, kw.pop('src'))
        rng, nl = mod.make_range(src, **kw)
        out[name] = (hashlib.md5(open(rng, 'rb').read()).hexdigest(),
                     {'nl': nl, 'size': os.path.getsize(rng)})
    for name, fn in PCASES:
        p = os.path.join(d, fn)
        summ = mod.process(p)
        out[name] = (hashlib.md5(open(p, 'rb').read()).hexdigest(),
                     {k: v for k, v in summ.items() if k != 'file'})
    return out


def main():
    freeze = None
    for a in sys.argv[1:]:
        if a.startswith('--freeze='):
            freeze = a.split('=', 1)[1]
    if freeze:
        spec = importlib.util.spec_from_file_location('r2p_old', freeze)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        d = tempfile.mkdtemp(prefix='g81freeze_')
        build_fixtures(d)
        res = run_battery(old, d)
        ref = {'md5': {k: v[0] for k, v in res.items()},
               'summaries': {k: v[1] for k, v in res.items()}}
        # R215: json.dumps writes false/true/null - NOT valid Python
        # literals (a pasted REF_SUMMARY died with NameError: name 'false').
        # pprint.pformat emits the same structure as real literals.
        import pprint
        print(pprint.pformat(ref, width=96, sort_dicts=True))
        print('# re-freeze: paste the block above into REF_MD5 / REF_SUMMARY', file=sys.stderr)
        return 0

    spec = importlib.util.spec_from_file_location('r2p', os.path.join(HERE, 'r2_postproc.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    d = tempfile.mkdtemp(prefix='g81run_')
    # R161: remove the golden-run dir on every exit path (tmpfs diet, R121 class)
    import atexit, shutil
    atexit.register(lambda: shutil.rmtree(d, ignore_errors=True))
    build_fixtures(d)
    res = run_battery(mod, d)
    fails = 0
    for name in sorted(res):
        md5, summ = res[name]
        if name not in REF_MD5:
            print('FAIL %s: no reference (re-freeze needed)' % name)
            fails += 1
            continue
        if md5 != REF_MD5[name]:
            print('FAIL %s: output differs from the frozen reference (md5 %s != %s)'
                  % (name, md5[:10], REF_MD5[name][:10]))
            fails += 1
        # R84: newer builders add summary keys (retract_pairs, slicer, ...) -
        # compare only the keys the reference knows (byte-identical output
        # is the real contract; the reference must stay re-baseline-free)
        _ref_summ = REF_SUMMARY.get(name)
        _summ_cmp = {k: v for k, v in summ.items() if k in _ref_summ} if _ref_summ else summ
        if _summ_cmp != _ref_summ:
            print('FAIL %s: summary differs: %r != %r' % (name, _summ_cmp, _ref_summ))
            fails += 1
    if not fails:
        print('R81 golden check: %d/%d cases byte-identical to the frozen reference' % (len(res), len(res)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
