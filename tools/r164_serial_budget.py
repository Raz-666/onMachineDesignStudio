#!/usr/bin/env python3
"""R164: MCU serial-budget audit - the 'Timer too close' firewall.

Two field shutdowns (.121/.122 logs) taught the budget the hard way:
the 250k-baud serial link is a SHARED resource - moves, LED frames,
TMC queries and heater polls all travel the same wire. A dense file
alone or a 24 fps LED animation alone fits; both together with a GC
pause does not.

This tool measures the move-message rate of every representative file
(the generated corpus + the 13 slicer dialects) in the worst 1-second
window, at file speed AND at the live-speed factors the user really
uses (125% / 150%), and compares it against the safe sustained serial
budget (~450 move messages/s at 250k baud, ~18-20 bytes each - the
same guard number audit_sweep uses per hop). Files that would eat more
than 60% of the budget at 150% get a WARN (headroom for heater polls,
TMC reads, resend bursts), above 100% a FAIL.

The LED side is covered by design since R163: the printing state is a
STATIC effect (klipper transmits only CHANGED colors = zero LED frames
while printing). For the record, the pre-.123 animated gradient at
24 fps plus its ~4% failed-readback resends cost an observed 50-150
msg/s of serial headroom - the .122 shutdown queue held 75/100 LED
messages. This tool re-checks that r2_printing stays static and no
frame_rate above 12 sneaks back in.

Run:  python3 tools/r164_serial_budget.py
Exit 0 = every file inside the budget + the LED diet intact.
"""
import math
import os
import re
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import r2_postproc as pp                                  # noqa: E402

# r110_gcode_dialects RUNS its whole suite at import (no __main__ guard) -
# exec its defs/tables only, up to the runner (the first `fails = []` line).
_src110 = open(os.path.join(HERE, 'r110_gcode_dialects.py'),
               encoding='utf-8').read()
_ns = {'__file__': os.path.abspath(os.path.join(HERE,
                                               'r110_gcode_dialects.py')),
       '__name__': 'r110_gcode_dialects_defs'}
exec(compile(_src110.split('\nfails = []', 1)[0], 'r110_gcode_dialects.py',
             'exec'), _ns)
DIALECTS = _ns['DIALECTS']
dialect_build = _ns['build']

BED = (0.0, -3.0, 220.0, 217.0)      # the real Ender-3 plate (manual ch. 23)

# safe sustained move-message budget on the 8-bit MCU serial link
BUDGET = 450.0                        # msg/s (250k baud, ~18-20 B per move)
WARN_AT = 0.60                        # headroom for polls/reads/resends

fails = []
warns = 0
runs = 0


# ---------------------------------------------------------------- sources --
def _png(path, w, h, fn):
    rows = b''
    for y in range(h):
        rows += b'\x00' + b''.join(bytes(fn(x, y)) for x in range(w))

    def chunk(t, d):
        c = t + d
        return (struct.pack('>I', len(d)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xffffffff))
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def photo_png(path, w=96, h=96):
    """organic single-row bands - the R162 litho killer shape"""
    def px(x, y):
        v = 128 + 90 * math.sin(x * 0.31 + 1.7) * math.cos(y * 0.23)
        v += 60 * math.sin((x + 2 * y) * 0.11)
        return (max(0, min(255, int(v))),) * 3
    _png(path, w, h, px)


def grad_png(path, w=64, h=64):
    _png(path, w, h, lambda x, y: (int(255 * (x / float(w - 1))),) * 3
         if y < h // 2 else (int(255 * (1 - x / float(w - 1))),) * 3)


# ---------------------------------------------------------------- measure --
MOVE_RE = re.compile(r'^G[01]\s')
AX_RE = re.compile(r'([XYZE])(-?[\d.]+)')
F_RE = re.compile(r'\bF([-\d.]+)')


def worst_window_rate(path, window=1.0, bucket=0.1):
    """worst move-message rate per second over sliding windows"""
    t = 0.0
    cur_f = 1200.0                     # slicers always set F before moving
    px = py = pz = pe = None
    buckets = {}
    n_moves = 0
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.split(';', 1)[0].strip()
        if not MOVE_RE.match(line):
            continue
        m = F_RE.search(line)
        if m:
            cur_f = abs(float(m.group(1)))
        ax = dict((k, float(v)) for k, v in AX_RE.findall(line))
        x = ax.get('X', px if px is not None else 0.0)
        y = ax.get('Y', py if py is not None else 0.0)
        z = ax.get('Z', pz if pz is not None else 0.0)
        e = ax.get('E', pe)
        if x is None and y is None and z is None and e is None:
            continue
        if cur_f <= 0:
            continue
        spd = cur_f / 60.0
        if px is None:
            dist = 0.0
        else:
            dist = math.sqrt((x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2)
        if e is not None and e != pe and dist == 0.0:
            dist = abs(e - (pe or 0.0))       # retract/unretract hop
        dur = max(dist / spd, 1e-4) if spd > 0 else 1e-4
        # one message per G0/G1; long segments occupy the wire for dur
        b = int(t / bucket)
        buckets[b] = buckets.get(b, 0) + 1
        n_moves += 1
        t += dur
        px, py, pz, pe = x, y, z, e
    if not buckets:
        return 0.0, 0
    n_b = int(round(window / bucket))
    keys = sorted(buckets)
    worst = 0
    for i in range(keys[0], keys[-1] + 1):
        w = sum(buckets.get(j, 0) for j in range(i, i + n_b))
        worst = max(worst, w)
    return worst / window, n_moves


def check(name, path):
    global warns, runs
    runs += 1
    rate, n = worst_window_rate(path)
    probs = []
    cells = []
    for f in (1.0, 1.25, 1.5):
        r = rate * f
        cells.append('%d%%:%4.0f/s' % (f * 100, r))
        if f == 1.5:
            if r > BUDGET:
                probs.append('%.0f msg/s at 150%% live speed - over the '
                             '%.0f/s serial budget (Timer-too-close risk)'
                             % (r, BUDGET))
            elif r > WARN_AT * BUDGET:
                warns += 1
    status = 'FAIL' if probs else ('WARN' if any(
        c.endswith('/s') and float(c.split(':')[1][:-2]) > WARN_AT * BUDGET
        for c in [cells[-1]]) else 'OK  ')
    if probs:
        fails.append((name, probs))
    print('%s %-46s moves=%-7d %s'
          % (status, os.path.basename(path)[:46], n, '  '.join(cells)))


# ------------------------------------------------------------------ corpus --
d = tempfile.mkdtemp(prefix='r164_')
src_photo = os.path.join(d, 'photo.png')
photo_png(src_photo)
src_grad = os.path.join(d, 'grad.png')
grad_png(src_grad)

print('==== R164 SERIAL BUDGET (moves/s in the worst 1s window; '
      'budget %.0f/s, warn > %.0f/s at 150%% live) ====' % (BUDGET,
                                                            WARN_AT * BUDGET))

# the generated corpus - every density class we ship
out, _ = pp.make_lithophane(src_photo, orient='FLAT', height_mm=60.0,
                            layer_h=0.2, levels=3, col_layers=2, bed=BED,
                            out_dir=d)
check('litho FLAT photo (R162 full fill)', os.path.join(d, out))

out, _ = pp.make_colorpic(src_grad, width_mm=80.0, bands=4, band_h=0.8,
                          bed=BED, out_dir=d)
check('colorpic gradient (R162 full fill)', os.path.join(d, out))

out, _ = pp.make_labels(['R2-D2', 'MACRO SYSTEM'], bed=BED, out_dir=d)
check('labels', os.path.join(d, out))

out, _ = pp.make_lithophane(src_grad, orient='STANDING', height_mm=60.0,
                            layer_h=0.2, bed=BED, out_dir=d)
check('litho STANDING (wavy zigzag)', os.path.join(d, out))

# the 13 slicer dialects (synthetic but style-true)
for i, dl in enumerate(DIALECTS):
    txt = dialect_build(dl)[0]
    p = os.path.join(d, 'dialect_%02d_%s.gcode' % (i, dl[0]))
    open(p, 'w').write(txt)
    check('dialect %s' % dl[0], p)

# -------------------------------------------------------------- LED diet --
runs += 1
led = open(os.path.join(os.path.dirname(HERE), 'macros', '03_leds.cfg'),
           encoding='utf-8').read()
printing_block = led.split('[led_effect r2_printing]')[1].split('[led_effect')[0]
m_fr = re.search(r'frame_rate:\s*(\d+)', printing_block)
pr_fr = int(m_fr.group(1)) if m_fr else 999
# R163: static = 0 msg/s (the .122 shutdown fix). R166: back to gentle
# motion - a slow breathing at <= 5 fps costs 5 msg/s = ~1% of the 450
# msg/s budget (a 3 s host stall queues 15 of 100 messages, not 72 like
# the old 24 fps). Anything faster than 5 fps while printing is a
# regression against the field log.
layer_line = [l.strip() for l in printing_block.splitlines()
              if l.strip().startswith(('static', 'breathing'))]
led_ok = ('frame_rate: 24' not in led and pr_fr <= 5
          and len(layer_line) == 1
          and layer_line[0].startswith(('static', 'breathing ')))
if not led_ok:
    fails.append(('LED diet (R163/R166)', ['r2_printing frame_rate %d '
                                           '(max 5) or its layer is not '
                                           'static/breathing' % pr_fr]))
print('%s %-46s <=%d LED msg/s while printing'
      % ('OK  ' if led_ok else 'FAIL', 'LED diet (printing animation)', pr_fr))

print('==== R164 SERIAL BUDGET: %d files measured, %d FAIL, %d warn ===='
      % (runs, len(fails), warns))
for (n, p) in fails:
    print('  FAIL %s: %s' % (n, '; '.join(p)))
sys.exit(1 if fails else 0)
