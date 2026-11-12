#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Raz-666 and contributors
"""r2_collect.py - the R2 evidence pack ("Doctor").

WHY THIS EXISTS (R252, field round .142g)
=========================================
Every MCU shutdown so far started with the same question: "how do I get the
log to you?" The downloads that used to work are gone (the WebUI export
button, the crash snapshots as .log files that Mainsail does not list), and
copying a 20 MB klippy.log by hand is exactly the friction that stopped the
last three rounds.

So this script builds ONE file that answers the questions before they are
asked: build stamps, host health, service states, the watcher's own state,
the settings, a compact INCIDENT DIGEST cut out of klippy.log (every
shutdown/probe failure with the 25 s around it, the worst reactor stalls
with their stacks, the MCU statistics), the last chunk of the raw log, the
newest MCU snapshot, the gcodes inventory and printer.cfg.

HOW IT RUNS
===========
  on the printer, no arguments needed:
      python3 ~/printer_data/config/klipper-e3-r2d2/tools/r2_collect.py
  from the LCD:  System > Diagnostics > "Log pack (for support)"
      (the macro sets a flag, the watcher builds the pack - no SSH)
  from the watcher itself: r2_postproc._doctor_tick()

WHERE IT LANDS
==============
  ~/printer_data/gcodes/crash_archive/R2-DOCTOR-<stamp>.txt   (the evidence)
  ~/printer_data/gcodes/crash_archive/R2-DOCTOR-<stamp>.gcode (the SAME file
      with a .gcode name - Mainsail/moonraker only LIST files it considers
      printable, which is why the old .log snapshots were invisible; the
      post-processor skips every R2-DOCTOR-* file, so it can never be
      printed or tagged by accident)

Read-only by design: nothing outside crash_archive/ is written, no sudo, no
service is touched. Safe while a print runs (only file reads), but the
watcher still builds it when idle - disk I/O during a print is the .125
lesson.
"""

import glob
import gzip
import os
import re
import shutil
import subprocess
import sys
import time

HOME = os.path.expanduser('~')
MAX_LOG_TAIL = 3 * 1024 * 1024        # raw klippy.log tail
MAX_TOTAL = 8 * 1024 * 1024           # hard cap for the whole pack
PACK_PREFIX = 'R2-DOCTOR-'


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _run(cmd, timeout=20, maxbytes=200000):
    """Run a shell command, never raise, cap the output."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        out = (p.stdout or b'') + (p.stderr or b'')
        txt = out.decode('utf-8', 'replace')
        if len(txt) > maxbytes:
            txt = txt[:maxbytes] + '\n[... truncated ...]\n'
        return txt.strip()
    except Exception as e:                              # noqa: BLE001
        return '(%s failed: %r)' % (cmd, e)


def _read(path, maxbytes=400000):
    try:
        with open(path, 'rb') as f:
            if maxbytes:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - maxbytes))
                data = f.read()
                return (data.decode('utf-8', 'replace') if size <= maxbytes
                        else '[... %d bytes skipped ...]\n' % (size - maxbytes)
                        + data.decode('utf-8', 'replace'))
            return f.read().decode('utf-8', 'replace')
    except Exception as e:                              # noqa: BLE001
        return '(%s unreadable: %r)' % (path, e)


def _guess_paths():
    """The field layout (/home/pi/printer_data); every path overridable."""
    pd = os.environ.get('R2_PRINTER_DATA') or os.path.join(HOME, 'printer_data')
    cfg = os.environ.get('R2_CONFIG_DIR') or os.path.join(pd, 'config')
    return {
        'pd': pd,
        'cfg': cfg,
        'logs': os.path.join(pd, 'logs'),
        'gcodes': os.path.expanduser(os.environ.get('R2_GCODES')
                                     or os.path.join(pd, 'gcodes')),
        'klippy_log': os.environ.get('R2_KLIPPY_LOG')
                      or os.path.join(pd, 'logs', 'klippy.log'),
        'vars': os.path.join(pd, 'variables.cfg'),
        'printer_cfg': os.path.join(cfg, 'printer.cfg'),
        'pkg': os.path.join(cfg, 'klipper-e3-r2d2'),
    }


# --------------------------------------------------------------------------
# the incident digest - the part that actually answers the questions
# --------------------------------------------------------------------------
_RE_BUSY = re.compile(r'^Reactor ([\d.]+) busy for ([\d.]+) with:', re.M)
_RE_STATS = re.compile(r'^Stats ([\d.]+):', re.M)


def _digest(log_text):
    """Everything a shutdown round needs, cut out of the raw log."""
    out = []
    lines = log_text.split('\n')

    # --- 1) the interesting lines, in order, with a little context.
    # The config dump in the log echoes every macro, so a plain keyword
    # search buries the events in RESPOND/G-Code text (measured on the
    # .142g field log: 83 hits, 40 of them config echo). The block between
    # '===== Config file =====' and the next rule is skipped entirely.
    pat = re.compile(r'shutdown|Timer too close|No trigger|Missed scheduling|'
                     r'Attempting MCU|Restarting printer|Start printer at|'
                     r'Klipper state|error during connect|Config error|'
                     r'Move queue|Unable to obtain|led update transmit|'
                     r'Neopixel update did not succeed|Log rollover', re.I)
    hits = []
    in_cfg = False
    for i, l in enumerate(lines):
        if l.startswith('===== Config file ====='):
            in_cfg = True
            continue
        if in_cfg:
            if l.startswith('======================='):
                in_cfg = False
            continue
        if pat.search(l):
            hits.append((i, l))
    out.append('### 1.1 events (%d lines matched)' % len(hits))
    for i, l in hits[:400]:
        out.append('%6d | %s' % (i + 1, l[:300]))
    if len(hits) > 400:
        out.append('[... %d more matched lines ...]' % (len(hits) - 400))

    # --- 2) reactor stalls, worst first, WITH their stacks
    stalls = []
    for m in _RE_BUSY.finditer(log_text):
        stamps = log_text[m.end():m.end() + 2600].split('\n')
        stack = [s.strip() for s in stamps[1:14] if s.strip().startswith(("- '", '-\t', '-'))]
        stalls.append((float(m.group(2)), m.group(1), stack))
    stalls.sort(reverse=True)
    out.append('')
    out.append('### 1.2 reactor stalls: %d total, worst 25 (with stacks)' % len(stalls))
    for dur, stamp, stack in stalls[:25]:
        out.append('  %.3fs at %s' % (dur, stamp))
        for s in stack:
            out.append('        %s' % s[:200])
    if stalls:
        over = [s for s in stalls if s[0] >= 0.25]
        out.append('  >>> %d stall(s) >= 0.25 s, %d >= 0.5 s, max %.3f s'
                   % (len(over), len([s for s in stalls if s[0] >= 0.5]), stalls[0][0]))
        culprits = {}
        for dur, _st, stack in stalls:
            for s in stack:
                key = s.split('(')[0].strip('- \t')
                culprits[key] = culprits.get(key, 0) + 1
        out.append('  >>> most frequent frames in stalls:')
        for k, v in sorted(culprits.items(), key=lambda kv: -kv[1])[:14]:
            out.append('        %4dx %s' % (v, k[:120]))

    # --- 3) the statistics around each shutdown + the last 40 stats lines
    shut = [m.start() for m in re.finditer(r"MCU '.*?' shutdown|Klipper state: Shutdown",
                                           log_text)]
    stats = [(m.start(), m.group(1)) for m in _RE_STATS.finditer(log_text)]
    out.append('')
    out.append('### 1.3 MCU statistics around the %d shutdown line(s)' % len(shut))
    for pos in shut[:4]:
        near = [s for s in stats if abs(s[0] - pos) < 6000][:6]
        out.append('  --- shutdown at offset %d ---' % pos)
        for p2, stamp in near:
            seg = log_text[p2:p2 + 700].split('\n')[0]
            keep = ['mcu_awake', 'print_time', 'buffer_time', 'print_stall',
                    'sysload', 'cputime', 'memavail', 'bytes_retransmit', 'srtt']
            vals = ' '.join(t for t in seg.split() if any(k in t for k in keep))
            out.append('    Stats %s: %s' % (stamp, vals[:340]))

    # --- 4) the tail of the shutdown paragraphs themselves
    out.append('')
    out.append('### 1.4 shutdown paragraphs (last 3)')
    for pos in shut[-3:]:
        out.append(log_text[max(0, pos - 1200):pos + 1800])
        out.append('  ' + '-' * 70)
    return '\n'.join(out)


# --------------------------------------------------------------------------
# the pack
# --------------------------------------------------------------------------
def _section(title):
    return '\n\n' + '=' * 78 + '\n== ' + title + '\n' + '=' * 78 + '\n'


def build_pack(gcodes_dir=None, out_dir=None, quiet=False):
    """Build the pack, return (txt_path, gcode_copy_path, size, n_sections)."""
    P = _guess_paths()
    if gcodes_dir:
        P['gcodes'] = os.path.expanduser(gcodes_dir)
    out_dir = os.path.expanduser(out_dir or os.path.join(P['gcodes'], 'crash_archive'))
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:                                   # noqa: BLE001
        out_dir = P['gcodes']

    stamp = time.strftime('%Y%m%d-%H%M%S')
    parts = []
    parts.append('R2-DOCTOR EVIDENCE PACK  %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    parts.append('Built by r2_collect.py on %s' % _run('hostname') or '?')
    parts.append('Send this ONE file - it carries versions, host health, services,')
    parts.append('settings, the klippy incident digest, the log tail, the newest MCU')
    parts.append('snapshot and printer.cfg. No sudo, nothing was changed.')

    # ---- versions -------------------------------------------------------
    parts.append(_section('1 VERSIONS / BUILD STAMPS'))
    ver = '?'
    for cf in (os.path.join(P['cfg'], 'macros', '01_state.cfg'),
               os.path.join(P['pkg'], 'macros', '01_state.cfg')):
        m = re.search(r"variable_version:\s*'([^']+)'",
                      _read(cf, 0) if os.path.isfile(cf) else '')
        if m:
            ver = m.group(1)
            parts.append('macros   : %s   (%s)' % (m.group(1), cf))
            break
    vf = os.path.join(P['pd'], 'variables.cfg')
    vv = _read(vf, 200000)
    for key in ('postproc_build', 'postproc_engine', 'pp_engine', 'recovery_mode',
                'doctor_nonce', 'doctor_done'):
        m = re.search(r"['\"]?%s['\"]?\s*:\s*([^,\n}]+)" % key, vv)
        if m:
            parts.append('%-9s: %s' % (key, m.group(1).strip()))
    parts.append('klipper  : %s' % _run(
        "cd ~/klipper 2>/dev/null && git describe --always --dirty 2>/dev/null || echo n/a"))
    parts.append('uname    : %s' % _run('uname -a'))
    parts.append('model    : %s' % _run(
        "tr -d '\\0' < /proc/device-tree/model 2>/dev/null || echo n/a"))

    # ---- host -----------------------------------------------------------
    parts.append(_section('2 HOST'))
    parts.append('uptime   : %s' % _run('uptime'))
    parts.append('free -m  :\n%s' % _run('free -m'))
    parts.append('df -h    :\n%s' % _run('df -h / /tmp'))
    parts.append('top 10 by CPU:\n%s' % _run(
        "ps -eo pcpu,pmem,etime,args --sort=-pcpu 2>/dev/null | head -11"))
    parts.append('r2 processes:\n%s' % _run("pgrep -af '[r]2_postproc.py' || echo none"))
    parts.append('throttled:\n%s' % _run('vcgencmd get_throttled 2>/dev/null || echo n/a'))
    parts.append('dmesg tail (may be empty without sudo):\n%s' % _run(
        'dmesg 2>/dev/null | tail -40'))

    # ---- services -------------------------------------------------------
    parts.append(_section('3 SERVICES'))
    for svc in ('klipper', 'moonraker', 'r2-postproc'):
        parts.append('--- %s ---' % svc)
        parts.append(_run('systemctl is-active %s 2>&1; systemctl status %s --no-pager '
                          '-n 0 2>&1 | head -14' % (svc, svc)))
    parts.append('--- r2-postproc journal (last 120 lines) ---')
    parts.append(_run('journalctl -u r2-postproc --no-pager -n 120 2>&1',
                      maxbytes=300000))
    parts.append('--- klipper journal errors (last 60) ---')
    parts.append(_run("journalctl -u klipper --no-pager -n 200 2>&1 | "
                      "grep -iE 'error|warn|shutdown|traceback' | tail -60",
                      maxbytes=200000))

    # ---- watcher state --------------------------------------------------
    parts.append(_section('4 WATCHER STATE'))
    for fn in ('watch_state.json', 'watcher_recovery.json'):
        for base in (P['pkg'], os.path.join(P['cfg'], 'klipper-e3-r2d2')):
            p = os.path.join(base, fn)
            if os.path.isfile(p):
                parts.append('%s:\n%s' % (p, _read(p, 60000)))
                break

    # ---- settings -------------------------------------------------------
    parts.append(_section('5 SETTINGS (variables.cfg - no secrets in it)'))
    parts.append(vv)

    # ---- klippy log -----------------------------------------------------
    parts.append(_section('6 KLIPPY LOG - INCIDENT DIGEST'))
    log = ''
    for cand in (P['klippy_log'], P['klippy_log'] + '.1'):
        if os.path.isfile(cand):
            log = _read(cand, 0)          # whole file for the digest
            parts.append('digest source: %s (%d bytes)' % (cand, len(log)))
            break
    if log:
        parts.append(_digest(log))
    else:
        parts.append('(no klippy.log found at %s)' % P['klippy_log'])

    parts.append(_section('7 KLIPPY LOG - RAW TAIL (last 3 MB)'))
    parts.append(_read(P['klippy_log'], MAX_LOG_TAIL))

    # ---- MCU snapshots --------------------------------------------------
    parts.append(_section('8 MCU SNAPSHOTS (crash_archive)'))
    arch = os.path.join(P['gcodes'], 'crash_archive')
    snaps = sorted(glob.glob(os.path.join(arch, 'mcu-*')))
    parts.append('folder: %s\n%d file(s):\n%s' % (
        arch, len(snaps), '\n'.join('  ' + os.path.basename(s) +
                                    '  %d B' % os.path.getsize(s) for s in snaps[-15:])))
    for s in snaps[-2:]:
        parts.append('--- %s (tail 3000 lines) ---' % os.path.basename(s))
        t = _read(s, 900000).split('\n')
        parts.append('\n'.join(t[-3000:]))
        tm = re.search(r'MCU .*shutdown: ([^\n]+)', _read(s, 900000))
        if tm:
            parts.append('  >>> first shutdown reason in this snapshot: %s' % tm.group(1))

    # ---- gcodes ---------------------------------------------------------
    parts.append(_section('9 GCODES FOLDER'))
    try:
        ent = []
        for root, dirs, files in os.walk(P['gcodes']):
            depth = root[len(P['gcodes']):].count(os.sep)
            if depth > 2:
                dirs[:] = []
                continue
            for f in files:
                p = os.path.join(root, f)
                try:
                    ent.append((os.path.getsize(p), p[len(P['gcodes']) + 1:]))
                except OSError:
                    pass
        ent.sort(reverse=True)
        parts.append('%d files, biggest 40:' % len(ent))
        for sz, nm in ent[:40]:
            parts.append('  %9d  %s' % (sz, nm))
    except Exception as e:                              # noqa: BLE001
        parts.append('(walk failed: %r)' % e)

    # ---- printer.cfg ----------------------------------------------------
    parts.append(_section('10 PRINTER.CFG'))
    parts.append(_read(P['printer_cfg'], 300000))

    text = '\n'.join(parts)
    if len(text) > MAX_TOTAL:
        text = text[:MAX_TOTAL] + '\n\n[... pack capped at %d bytes ...]\n' % MAX_TOTAL

    base = os.path.join(out_dir, PACK_PREFIX + stamp)
    txt_path = base + '.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    # The .gcode twin: Mainsail/the stock SD list only show files they consider
    # printable - that is exactly why the old .log snapshots were invisible.
    gcode_path = base + '.txt.gcode'
    try:
        shutil.copyfile(txt_path, gcode_path)
    except Exception:                                   # noqa: BLE001
        gcode_path = ''
    if not quiet:
        print('pack: %s (%d bytes)' % (txt_path, len(text)))
        if gcode_path:
            print('download copy: %s' % gcode_path)
    return txt_path, gcode_path, len(text), text.count('== ')


def main():
    out = None
    for a in sys.argv[1:]:
        if a.startswith('--out='):
            out = a.split('=', 1)[1]
        elif a in ('-h', '--help'):
            print(__doc__)
            return 0
    txt, gc, size, nsec = build_pack(out_dir=out)
    print('\nDownload it in Mainsail: Dateien -> crash_archive -> %s'
          % os.path.basename(gc or txt))
    return 0


if __name__ == '__main__':
    sys.exit(main())
