#!/usr/bin/env python3
"""Fix: Klipper 'invalid syntax (gcode_shell_command.py, line N)' at connect.

Root cause: klippy/extras/gcode_shell_command.py itself is INVALID PYTHON
(corrupted/foreign copy). Klipper loads that module ONLY when at least one
[gcode_shell_command] section is active in the config - and refuses to boot
with 'Internal error during connect: invalid syntax (gcode_shell_command.py,
line N)' if the module file is broken.

This tool:
  1. checks the gcode_shell_command.py module file (valid Python?),
  2. if INVALID: removes EVERY [gcode_shell_command ...] section from every
     *.cfg in the config dir (with a .r2bak backup) so the broken module is
     never loaded - Klipper boots cleanly,
  3. if VALID: does nothing (the sections work as-is).

The gcode_shell_command features (LCD persist R2_PERSIST, audio R2_AUDIO_PLAY,
and any other shell-command section) are then DISABLED - install/fix the
module (KIAUH) to bring them back.

Run on the printer (after unpacking the release ZIP):
    python3 <unpacked>/klipper-e3-r2d2/tools/fix_gcode_shell_command.py
    # or with a specific config dir:
    python3 <unpacked>/klipper-e3-r2d2/tools/fix_gcode_shell_command.py /home/pi/printer_data/config
"""
import os
import re
import sys
import glob
import shutil


def compile_py(src):
    try:
        compile(src, "<gcode_shell_command.py>", "exec")
        return None
    except SyntaxError as e:
        return "invalid Python: %s (line %s)" % (e.msg, e.lineno)


def find_module():
    for base in (os.path.expanduser("~/klipper"),
                 os.path.expanduser("~/printer_data"),
                 os.path.expanduser("~/rpi-klipper"),
                 "/home/pi/klipper"):
        p = os.path.join(base, "klippy/extras/gcode_shell_command.py")
        if os.path.isfile(p):
            return p
    return None


def remove_sections(cfg_dir):
    """Remove every [gcode_shell_command ...] block from each *.cfg."""
    # match header + body (body = lines until next '[' section header or EOF)
    block_re = re.compile(r'\[gcode_shell_command\s+[^\]]+\][^\[]*', re.S)
    removed = 0
    files = sorted(glob.glob(os.path.join(cfg_dir, "**", "*.cfg"), recursive=True))
    for p in files:
        s = open(p, errors="replace").read()
        # only touch files that actually have the sections
        if '[gcode_shell_command' not in s:
            continue
        n = len(block_re.findall(s))
        if n == 0:
            continue
        backup = p + ".r2bak"
        if not os.path.exists(backup):
            shutil.copy2(p, backup)
        s2 = block_re.sub("", s)
        # collapse 3+ blank lines left by removal
        s2 = re.sub(r'\n{3,}', '\n\n', s2)
        open(p, "w", encoding="utf-8", errors="surrogateescape").write(s2)
        removed += n
        print("  [removed] %s  (%d section(s)) - backup: %s" % (os.path.relpath(p, cfg_dir), n, os.path.basename(backup)))
    return removed


def main():
    cfg_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/printer_data/config")
    print("=== gcode_shell_command fix ===")
    print("config dir: %s" % cfg_dir)
    print("--- 1. module ---")
    mod = find_module()
    if mod is None:
        print("[module] gcode_shell_command.py NOT FOUND at usual paths")
        print("         no [gcode_shell_command] section can work - removing them")
    else:
        src = open(mod, errors="replace").read()
        err = compile_py(src)
        print("[module] %s" % mod)
        if err is None:
            print("  [OK] module is valid Python - nothing to fix, sections work")
            print("       (if the connect error still occurs, restart Klipper)")
            return 0
        print("  [BAD] %s" % err)
        print("       -> the module file itself is broken. Removing all")
        print("          [gcode_shell_command] sections so it is not loaded.")
    print("--- 2. removing sections ---")
    if not os.path.isdir(cfg_dir):
        print("[configs] DIR NOT FOUND: %s" % cfg_dir)
        print("          pass the config dir as argument, e.g.")
        print("          python3 tools/fix_gcode_shell_command.py /home/pi/printer_data/config")
        return 1
    removed = remove_sections(cfg_dir)
    print("--- result ---")
    print("Removed %d [gcode_shell_command] section(s)." % removed)
    print("Restart Klipper - the connect error is gone.")
    print("To re-enable the shell-command features, install/fix the module")
    print("(KIAUH provides gcode_shell_command.py) and re-add the sections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
