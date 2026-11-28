#!/usr/bin/env python3
"""Diagnose: locate the gcode_shell_command that breaks Klipper's connect.

Symptom: 'Internal error during connect: invalid syntax
(gcode_shell_command.py, line N)'.

Klipper-native klippy/extras/gcode_shell_command.py COMPILES every
[gcode_shell_command NAME] 'command:' value as Python at connect (the filename
'gcode_shell_command.py' and the line in the error refer to the compiled
command string, NOT to your config line). A command that is a shell string
('bash /path') or any invalid Python trips exactly this error.

This tool:
  1. checks the gcode_shell_command.py MODULE itself (a corrupted/foreign copy
     would also report 'invalid syntax' at that file's line),
  2. scans EVERY *.cfg in the config dir for [gcode_shell_command ...] sections
     and compiles each command: value (multi-line aware) as Python,
  3. prints the offending section + the exact fix.

Run on the printer (or against any config dir):
    python3 tools/diag_shell_command.py [CONFIG_DIR]
Default CONFIG_DIR: ~/printer_data/config (also probes ~/klipper/klippy/extras
for the module).
"""
import os, re, sys, glob

def compile_py(src, fname="<command>"):
    try:
        compile(src, fname, "exec")
        return None
    except SyntaxError as e:
        return "invalid Python: %s (line %s)" % (e.msg, e.lineno)

def check_module():
    candidates = []
    for base in [os.path.expanduser("~/klipper"), os.path.expanduser("~/printer_data"),
                 os.path.expanduser("~/rpi-klipper"), "/home/pi/klipper"]:
        for sub in ("klippy/extras/gcode_shell_command.py",
                    "klippy/extras/gcode_shell_command.py"):
            candidates.append(os.path.join(base, sub))
    for p in candidates:
        if os.path.isfile(p):
            src = open(p, errors="replace").read()
            err = compile_py(src, p)
            print("[module] %s" % p)
            if err:
                print("  [BAD] %s  ->  THE MODULE ITSELF IS INVALID PYTHON" % err)
                print("  -> replace it with a clean Klipper copy, or remove any")
                print("     [gcode_shell_command] sections from your config so it is")
                print("     not loaded at all.")
                return True
            else:
                print("  [OK] module compiles")
            return False
    print("[module] gcode_shell_command.py not found at usual paths")
    print("         (if you have [gcode_shell_command] sections active, Klipper")
    print("          needs this file - install KIAUH or Klipper's native extra).")
    return False

def check_configs(cfg_dir):
    bad = 0
    total = 0
    if not os.path.isdir(cfg_dir):
        print("[configs] DIR NOT FOUND: %s" % cfg_dir)
        print("          pass the config dir as argument, e.g.")
        print("          python3 tools/diag_shell_command.py /home/pi/printer_data/config")
        return bad
    for p in sorted(glob.glob(os.path.join(cfg_dir, "**", "*.cfg"), recursive=True)):
        rel = os.path.relpath(p, cfg_dir)
        lines = open(p, errors="replace").read().split("\n")
        i = 0
        while i < len(lines):
            m = re.match(r'^\[gcode_shell_command\s+([^\]]+)\]', lines[i])
            if m:
                sec = m.group(1).strip()
                # gather the command block (multi-line)
                j = i + 1
                cmd_lines = []
                while j < len(lines):
                    l = lines[j]
                    if re.match(r'^\[(?!gcode_shell_command)[^\]]+\]', l):
                        break
                    cm = re.match(r'^(\s*)command:\s*(.*)$', l)
                    if cm:
                        indent = cm.group(1)
                        cmd_lines.append(cm.group(2))
                        j += 1
                        # continuation lines (indented, not a new key, not a section)
                        while j < len(lines):
                            nl = lines[j]
                            if re.match(r'^\[', nl):
                                break
                            if re.match(r'^\s*\S+:', nl) and not nl.lstrip().startswith('#'):
                                break
                            if nl.strip() == "" or nl.lstrip().startswith('#'):
                                break
                            cmd_lines.append(nl[len(indent):] if nl.startswith(indent) else nl)
                            j += 1
                        break
                    j += 1
                if cmd_lines:
                    total += 1
                    val = "\n".join(cmd_lines)
                    val = re.sub(r'\s+#.*$', '', val, flags=re.S).strip()
                    err = compile_py(val, "<%s>" % sec)
                    if err:
                        bad += 1
                        print("\n[BAD] %s  [gcode_shell_command %s]" % (rel, sec))
                        print("      config line %d, command %d line(s)" % (i + 1, len(val.splitlines())))
                        print("      -> %s" % err)
                        print("      cmd: %r" % val[:300])
                        print("      FIX: make the command VALID PYTHON, e.g.")
                        print("           __import__('subprocess').check_call(['bash', '<script>'])")
                        print("      OR remove the section if you do not need it.")
                i = j
                continue
            i += 1
    print("\n[configs] %d [gcode_shell_command] section(s) checked, %d BAD" % (total, bad))
    return bad

if __name__ == "__main__":
    cfg_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/printer_data/config")
    print("=== gcode_shell_command diagnose ===")
    print("config dir: %s" % cfg_dir)
    print("--- 1. module ---")
    check_module()
    print("--- 2. configs ---")
    bad = check_configs(cfg_dir)
    print("\n=== RESULT ===")
    if bad:
        print("Found %d invalid command(s) - fix the [BAD] section(s) above." % bad)
        sys.exit(1)
    print("No invalid command found. If the error persists, check that the")
    print("module itself compiles (section 1) and that no [gcode_shell_command]")
    print("section is commented-in unexpectedly, then restart Klipper.")
    sys.exit(0)
