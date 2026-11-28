#!/usr/bin/env python3
"""Strip ALL LED-related content from the R2 config macros/menus.

Safe approach:
  1. removes standalone LED command lines (leaf commands - Jinja balance safe)
  2. reports remaining LED-var Jinja references so multi-line guard blocks
     can be handled explicitly (balance-critical)

Run: python3 tools/strip_leds.py [--apply]
Without --apply it only reports what it would remove.
"""
import re, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MACROS = os.path.join(ROOT, "macros")
MENUS = os.path.join(ROOT, "menus")

# standalone LED command lines (leaf gcode - safe to drop line-wise)
LED_CMD = re.compile(
    r"^\s*(SET_LED_STATE\s|SET_LED_EFFECT\s|STOP_LED_EFFECTS\b|SET_LED\s|"
    r"_LED_QUIET\s|_COLORPIC_LED_APPLY\s|LED_INFO\b|TEST_LEDS\b|TOGGLE_LEDS\b|"
    r"SET_LED_LAYOUT\s|SET_NOZZLE_SPLIT\s|SET_BED_LIGHT\s|_NOZZLE_SET\s|"
    r"_BEDLIGHT_SET\s|_LED_JOB_PROGRESS\s|_LED_JOB_DONE\s|NOZZLE_LED\s)"
)
# LED-var Jinja references (need block-aware handling)
LED_VAR = re.compile(
    r"leds_on|led_enabled|led_section|led_type|led_status_n|led_bed_n|"
    r"led_nozzle_split|led_nozzle_section|led_bright|led_nozzle|led_bed|"
    r"has_eff|'led_effect|led_effect r2_|R2_PERSIST|printer_leds|nozzle_led"
)

targets = []
for d in (MACROS, MENUS):
    for f in sorted(os.listdir(d)):
        if f.endswith(".cfg") and f != "03_leds.cfg":
            targets.append(os.path.join(d, f))

def process(path, apply):
    s = open(path, errors="replace").read()
    lines = s.split("\n")
    kept = []
    removed = 0
    for ln in lines:
        if LED_CMD.match(ln):
            removed += 1
            if not apply:
                print("  [would drop] %s: %s" % (os.path.relpath(path, ROOT), ln.strip()))
            continue
        kept.append(ln)
    if apply and removed:
        open(path, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(kept))
    # report remaining LED-var refs (block handling needed)
    remaining = [ln for ln in kept if LED_VAR.search(ln)]
    return removed, remaining

total = 0
all_remaining = {}
for p in targets:
    r, rem = process(p, "--apply" in sys.argv)
    total += r
    if rem:
        all_remaining[p] = rem
print("standalone LED command lines removed: %d" % total)
print("\n=== remaining LED-var Jinja references (need block-aware handling) ===")
for p, rem in all_remaining.items():
    print("  %s (%d)" % (os.path.relpath(p, ROOT), len(rem)))
    for ln in rem[:40]:
        print("      %s" % ln.strip()[:120])
