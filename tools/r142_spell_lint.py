#!/usr/bin/env python3
"""R142: spelling lint over every USER-FACING string in the project.

User-facing = the words that end up on the LCD, in Mainsail/fluidd
consoles or in file headers:
  - NOTIFY TEXT="..." / RESPOND MSG="..." / M117 lines in all macros
  - [gcode_macro] description: lines
  - menu item / entry name: lines in the LCD menus
  - generator info headers ('; note:' etc. in r2_postproc output)

Gcode comments and code identifiers are NOT user-facing and skipped.
Words inside Jinja expressions ({...}) are placeholders, not prose.

Uses pyspellchecker (en) when available - otherwise a pure consistency
pass (a rare word with edit-distance 1 from a 3x+ more frequent word is
a typo suspect). Exit 0 = clean.

  pip3 install pyspellchecker   # optional but recommended
"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAC_DIR = os.path.join(ROOT, 'macros')
TOOL = os.path.join(HERE, 'r2_postproc.py')

# things the dictionary does not know but we mean them
WHITELIST = set('''
klipper mainsail moonraker fluidd orca prusa superslicer cura
mcu tmc pid pa bedell macro macros gcode gcodes m117 m104 m109 m106 m107
m600 m190 m140 m84 m112 heatmap idex
lcd neopixel pwm neopixels leds cfg jinja
plla pla abs petg asa tpu pc ppa
pidfine tunez brim vase litho lithophane colorpic
backslash retraction unretract deretraction retract retfix
e-step esteps e-steps z-offset zoffset
hotend homing homed unhomed
sdcard usbstick
r2d2 r2-info gcode_macro
timestamps timecode timestep
spi i2c uart
v01 v02 gcode-file
configfile configfiles
buildplate buildplates
kamp voron ender
fmm gmm src compat freq seg png jpg csv txt bak plt obj
accels accel decel acc sys mzv deg vel pos cond incl blk
testz stopat rect ishaper bandh penz fanl wht gry blk
re-heats re-inserting re-applied dockable cpu mate mating hands hats feet scaled cell cells
pre post vol
'''.split())

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")


def user_strings():
    """yield (origin, text) for every user-facing string"""
    for fn in sorted(os.listdir(MAC_DIR)):
        if not fn.endswith('.cfg'):
            continue
        path = os.path.join(MAC_DIR, fn)
        for ln, line in enumerate(open(path, encoding='utf-8'), 1):
            t = line.strip()
            origin = '%s:%d' % (fn, ln)
            m = re.match(r'^(?:NOTIFY|RESPOND)\s+(?:TEXT|MSG)\s*=\s*"(.*)"',
                         t)
            if m:
                yield origin, m.group(1)
                continue
            m = re.match(r'^M117\s+(.*)$', t)
            if m:
                yield origin, m.group(1)
                continue
            m = re.match(r'^description:\s*(.*)$', t)
            if m:
                yield origin, m.group(1)
                continue
            # menu lines: name: / item: / greeting on the LCD
            if re.match(r'^\[menu ', t):
                cur_menu = t
                continue
            m = re.match(r'^(?:name|item|greeting):\s*(.+)$', t)
            if m:
                yield origin, m.group(1)
    # generator notes (info the user reads in the file header / console)
    txt = open(TOOL, encoding='utf-8').read()
    for m in re.finditer(r"notes\.append\(\s*'([^']{12,})'", txt):
        yield 'r2_postproc:notes', m.group(1)
    for m in re.finditer(r"NOTIFY TEXT=\"([^\"]{10,})\"", txt):
        yield 'r2_postproc:notify', m.group(1)


def words_of(text):
    # drop jinja expressions and {placeholders} first
    text = re.sub(r'\{[^{}]*\}', ' ', text)
    # drop bare numbers/units
    for w in WORD_RE.findall(text):
        w = w.strip("'-").lower()
        if len(w) >= 3:
            yield w


def edit1(a, b):
    """True if a,b differ by exactly one edit (sub/ins/del)"""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    if len(a) > len(b):
        a, b = b, a
    # a shorter: one insertion in a gives b
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def main():
    try:
        from spellchecker import SpellChecker
        sp = SpellChecker(distance=1)
        have_dict = True
    except ImportError:
        sp = None
        have_dict = False
        print('[r142] pyspellchecker not installed - consistency pass only'
              ' (pip3 install pyspellchecker)')

    freq = Counter()
    per_origin = []
    for origin, text in user_strings():
        ws = list(words_of(text))
        freq.update(ws)
        per_origin.append((origin, text, ws))

    problems = []
    for origin, text, ws in per_origin:
        for w in ws:
            if w in WHITELIST or any(c.isdigit() for c in w):
                continue
            bad = False
            hint = ''
            if have_dict and w not in sp:
                # correction must be plausible: suggest only if an edit1
                # neighbour exists (dictionary false positives on tech
                # terms are common - the whitelist + distance guard
                # keeps this quiet)
                cand = sp.candidates(w) if hasattr(sp, 'candidates') else []
                near = [c for c in (cand or []) if c and edit1(w, c)]
                if near:
                    bad = True
                    hint = '-> ' + ','.join(sorted(near)[:3])
            elif not have_dict:
                for other, n in freq.items():
                    if other != w and n >= 3 and freq[w] == 1 \
                            and edit1(w, other):
                        bad = True
                        hint = '-> %s (x%d)' % (other, n)
                        break
            if bad:
                problems.append((origin, w, hint, text[:70]))

    n = len(per_origin)
    if problems:
        print('R142 SPELL LINT: %d user-facing strings, %d suspects'
              % (n, len(problems)))
        for (o, w, h, t) in problems:
            print('  %-34s %-16s %-24s | %s' % (o, w, h, t))
        sys.exit(1)
    print('R142 SPELL LINT: %d user-facing strings, 0 suspects (%s)'
          % (n, 'dictionary' if have_dict else 'consistency'))
    sys.exit(0)


if __name__ == '__main__':
    main()
