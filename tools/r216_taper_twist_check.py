#!/usr/bin/env python3
"""R216 taper + twist check (pinned).

TAPER (.136n user wish) rides in the Scale X/Y channel: scale_top_x/
scale_top_y (percent, 0 = off) interpolate linearly in Z over the
EXTRUDING z-span of the file (travel hops must not water the top factor
down), E is recomputed per move, the filename carries the taper
(..._S100-100T60-60.gcode). TWIST is its OWN tool: twist_deg (0 at the
bottom -> deg at the top, sign = direction, |deg| 0.5..720), the object
rotates around its center onto the bed center, E stays verbatim
(rotation is isometric), arcs become chords with the E split by chord
length, the filename carries the angle (..._TWR90.gcode, Twist/ folder).

Pins:
  - SCALE_APPLY: TOP_X/TOP_Y save + taper speak, range guard, the
    100/100-nothing guard now requires "no taper" too
  - TWIST_APPLY: arm/second press, range + 0-deg + small-angle guards,
    no-file guard, the nonce bump
  - LCD: Scale menu grows Top X/Top Y inputs, a Twist list (deg/how/go)
    sits between Scale and Cut&Split
  - engine taper: filename, bottom keeps the size, top reaches the top
    factor, E drops with the removed material, uniform stays untouched,
    the old 100/100 guard refuses, out-of-range refuses
  - engine twist: filename/folder, E verbatim (isometric), the top wall
    polygon IS the bottom polygon rotated, guards refuse, twist after
    scale (taper+twist combined) works
  - travel golden rule: 0 flat ink crossings in every output

Run:  python3 tools/r216_taper_twist_check.py
"""
import importlib.util
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jinja2 import Environment, Undefined, BaseLoader   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PASS = []
FAIL = []


def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  [%s]' % detail) if detail and not ok else ''))


spec = importlib.util.spec_from_file_location(
    'r2p', os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# ---------------- macro rendering -------------------------------------------
env = Environment(loader=BaseLoader(),
                  variable_start_string='{', variable_end_string='}',
                  block_start_string='{%', block_end_string='%}',
                  comment_start_string='{#', comment_end_string='#}',
                  trim_blocks=True, lstrip_blocks=False, undefined=Undefined)
gsrc = open(os.path.join(ROOT, 'macros/17_generator.cfg'),
            encoding='utf-8').read()


def body(name):
    m = re.search(r'\[gcode_macro %s\](.*?)(?=\n\[)' % re.escape(name),
                  gsrc, re.S)
    b = re.search(r'gcode:\n((?:[ \t]+.*\n?)*)', m.group(1))
    return b.group(1)


class M(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


def render(name, sv_over=None, params=None):
    sv = {'scale_x': 100, 'scale_y': 100, 'scale_top_x': 0,
          'scale_top_y': 0, 'twist_deg': 0, 'scale_nonce': 5,
          'twist_nonce': 5, 'preview_file': 'part.gcode'}
    sv.update(sv_over or {})
    printer = M({'save_variables': M({'variables': M(sv)}),
                 'gcode_macro _STATE': M({'mode': 'idle', 'gen_arm': ''})})
    env.globals['printer'] = printer
    env.globals['params'] = params or {}
    return env.from_string(body(name)).render()


out = render('SCALE_APPLY', params={'X': '100', 'Y': '100'})
ck('macro: 100/100 without a taper still refuses (nothing to do)',
   'changes nothing' in out and 'VARIABLE=scale_nonce VALUE=6' not in out,
   out[:90])
out = render('SCALE_APPLY', params={'X': '100', 'Y': '100',
                                    'TOP_X': '60', 'TOP_Y': '60'})
ck('macro: 100/100 WITH a taper runs - saves top factors + speaks them',
   'VARIABLE=scale_top_x VALUE=60' in out
   and 'VARIABLE=scale_top_y VALUE=60' in out
   and 'tapering to 60%%/60%% at the top' in out
   and 'VARIABLE=scale_nonce VALUE=6' in out, out[:160])
out = render('SCALE_APPLY', params={'X': '120', 'Y': '100', 'TOP_X': '400'})
ck('macro: TOP_X out of range refuses (0 or 25..300)',
   'TOP_X/TOP_Y must be 0 (off) or 25..300' in out
   and 'VARIABLE=scale_nonce VALUE=6' not in out, out[:110])
out = render('SCALE_APPLY', params={'X': '120', 'Y': '100'})
ck('macro: plain scale stays the same (no taper speak)',
   'VARIABLE=scale_top_x VALUE=0' in out and 'tapering to' not in out
   and 'VARIABLE=scale_nonce VALUE=6' in out, out[:110])

out = render('TWIST_APPLY', params={'CONFIRM': '1', 'DEG': '90'})
ck('macro: TWIST first press ARMS (no nonce bump yet)',
   '_GEN_ARM KEY=twist' in out and 'VARIABLE=twist_nonce' not in out,
   out[:110])


def render_armed(name, sv_over=None, params=None):
    sv = {'scale_x': 100, 'scale_y': 100, 'scale_top_x': 0,
          'scale_top_y': 0, 'twist_deg': 0, 'scale_nonce': 5,
          'twist_nonce': 5, 'preview_file': 'part.gcode'}
    sv.update(sv_over or {})
    printer = M({'save_variables': M({'variables': M(sv)}),
                 'gcode_macro _STATE': M({'mode': 'idle',
                                           'gen_arm': 'twist'})})
    env.globals['printer'] = printer
    env.globals['params'] = params or {}
    return env.from_string(body(name)).render()


out = render_armed('TWIST_APPLY', params={'CONFIRM': '1', 'DEG': '90'})
ck('macro: TWIST second press = _GEN_GO + saves + bumps the nonce',
   '_GEN_GO KEY=twist' in out
   and re.search(r'VARIABLE=twist_deg VALUE=90\.0', out)
   and ('VARIABLE=twist_file VALUE=' + chr(34) + chr(92) + chr(34) + 'part.gcode') in out
   and 'VARIABLE=twist_nonce VALUE=6' in out, out[:160])
out = render('TWIST_APPLY', params={'DEG': '0'})
ck('macro: 0 deg refuses (nothing to do)',
   'changes nothing' in out and 'VARIABLE=twist_nonce' not in out,
   out[:90])
out = render('TWIST_APPLY', params={'DEG': '900'})
ck('macro: |deg| > 720 refuses', 'must be -720..720' in out
   and 'VARIABLE=twist_nonce' not in out, out[:90])
out = render('TWIST_APPLY', params={'DEG': '0.2'})
ck('macro: |deg| < 0.5 refuses (wall slivers)',
   'below 0.5' in out and 'VARIABLE=twist_nonce' not in out, out[:90])
out = render('TWIST_APPLY', params={'DEG': '45'},
             sv_over={'preview_file': ''})
ck('macro: no file selected refuses honestly',
   'no file selected' in out and 'VARIABLE=twist_nonce' not in out,
   out[:90])

# ---------------- LCD wiring -------------------------------------------------
lcd = open(os.path.join(ROOT, 'menus/lcd_menues.cfg'),
           encoding='utf-8').read()
ck('lcd: Scale menu carries Top X / Top Y inputs (0..300, step 5)',
   '[menu __main __preprint __mods __scale __topx]' in lcd
   and '[menu __main __preprint __mods __scale __topy]' in lcd
   and lcd.count('SAVE_VARIABLE VARIABLE=scale_top_x VALUE='
                 '{menu.input|round|int}') == 1, '')
ck('lcd: Twist list (deg/how/go) sits between Scale and Cut&Split',
   '[menu __main __preprint __mods __twist]' in lcd
   and '[menu __main __preprint __mods __twist __deg]' in lcd
   and '[menu __main __preprint __mods __twist __go]' in lcd
   and 'TWIST_APPLY CONFIRM=1' in lcd
   and lcd.index('__mods __twist]') < lcd.index('__mods __cake]'), '')
ck('lcd: watcher wiring - twist channel + scale top factors present',
   "'twist_nonce'" in open(os.path.join(
       HERE, 'r2_postproc.py'), encoding='utf-8').read()
   and "'twist': 'Twist'" in open(os.path.join(
       HERE, 'r2_postproc.py'), encoding='utf-8').read(), '')

# ---------------- helpers ----------------------------------------------------
def esum(path):
    x_e = 0.0
    tot = 0.0
    e_rel = False
    for ln in open(path, errors='replace').read().split('\n'):
        code = ln.split(';', 1)[0].strip()
        if not code:
            continue
        parts = code.split()
        cmd = parts[0].upper()
        if cmd == 'M83':
            e_rel = True
            continue
        if cmd == 'M82':
            e_rel = False
            continue
        if cmd == 'G92':
            for p in parts[1:]:
                if p[:1].upper() == 'E':
                    try:
                        x_e = float(p[1:])
                    except ValueError:
                        pass
            continue
        if cmd not in ('G0', 'G1', 'G2', 'G3'):
            continue
        for p in parts[1:]:
            if p[:1].upper() == 'E':
                try:
                    v = float(p[1:])
                except ValueError:
                    continue
                tot += (v if e_rel else v - x_e)
                x_e = v if not e_rel else x_e
    return tot


def wall_points_at(path, z):
    """the FIRST extruding moves at z = the outer wall loop (corners)."""
    x = y = cz = 0.0
    pts = []
    for ln in open(path, errors='replace').read().split('\n'):
        code = ln.split(';', 1)[0].strip()
        if not code or not code.startswith(('G0', 'G1')):
            continue
        nx = ny = nz = ne = None
        for p in code.split()[1:]:
            q = p[:1].upper()
            try:
                v = float(p[1:])
            except ValueError:
                continue
            if q == 'X':
                nx = v
            elif q == 'Y':
                ny = v
            elif q == 'Z':
                nz = v
            elif q == 'E':
                ne = v
        if nz is not None:
            cz = nz
        if nx is not None:
            x = nx
        if ny is not None:
            y = ny
        if ne is not None and ne > 0 and abs(cz - z) < 0.06:
            pts.append((x, y))
            if len(pts) >= 8:
                return pts
    return pts


def span_at(path, z):
    pts = wall_points_at(path, z)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    return (min(xs), max(xs))


def audit(path):
    x = y = z = 0.0
    e = 0.0
    e_rel = False
    retracted = False
    extr = {}
    viol = []
    for ln in open(path, errors='replace').read().split('\n'):
        code = ln.split(';', 1)[0].strip()
        if not code:
            continue
        parts = code.split()
        cmd = parts[0].upper()
        if cmd == 'M83':
            e_rel = True
            continue
        if cmd == 'M82':
            e_rel = False
            continue
        if cmd == 'G10':
            retracted = True
            continue
        if cmd == 'G11':
            retracted = False
            continue
        if cmd == 'G92':
            for p in parts[1:]:
                if p[:1].upper() == 'E':
                    try:
                        e = float(p[1:])
                    except ValueError:
                        pass
            continue
        if cmd not in ('G0', 'G1'):
            continue
        nx = ny = nz = ne = None
        for p in parts[1:]:
            q = p[:1].upper()
            try:
                v = float(p[1:])
            except ValueError:
                continue
            if q == 'X':
                nx = v
            elif q == 'Y':
                ny = v
            elif q == 'Z':
                nz = v
            elif q == 'E':
                ne = v
        px, py, pz = x, y, z
        if nx is not None:
            x = nx
        if ny is not None:
            y = ny
        if nz is not None:
            z = nz
        de = 0.0
        if ne is not None:
            de = (ne - e) if not e_rel else ne
            e = ne if not e_rel else e + ne
        dd = math.hypot(x - px, y - py)
        if de > 0 and dd > 1e-4:
            extr.setdefault(round(pz, 3), []).append((px, py, x, y))
            retracted = False
        elif dd > 0.05 and (nz is None or abs(nz - pz) < 0.06):
            if not retracted:
                tvx, tvy = x - px, y - py
                tl = math.hypot(tvx, tvy) or 1.0
                tvx, tvy = tvx / tl, tvy / tl
                hits = 0
                for (a, b, c, d2) in extr.get(round(z, 3), ()):
                    if pp._segs_cross((px, py), (x, y), (a, b), (c, d2)):
                        sx, sy = c - a, d2 - b
                        sl = math.hypot(sx, sy) or 1.0
                        if abs(tvx * sx / sl + tvy * sy / sl) > 0.90:
                            continue
                        hits += 1
                        if hits > 2:
                            break
                if hits > 2 and dd >= 0.25:
                    viol.append((round(z, 2), code[:36]))
    return viol


# ---------------- engine: taper ----------------------------------------------
d = tempfile.mkdtemp(prefix='r216tap_')
for sub in ('Shapes', 'Scale', 'Twist'):
    os.makedirs(os.path.join(d, sub), exist_ok=True)
src, _ = pp.make_shape(shape='SQUARE', size_x=40, size_y=40, height=10,
                       walls=2, infill=20, base=3, top=3,
                       out_dir=os.path.join(d, 'Shapes'), version=1)
zt = 0.28 + 49 * 0.2          # the top layer of a 10mm object @ 0.2

tap, si = pp.apply_scale(src, sx=1.0, sy=1.0, sxt=0.6, syt=0.6,
                         out_dir=os.path.join(d, 'Scale'))
sb = span_at(tap, 0.28)
st = span_at(tap, zt)
ck('taper: filename carries the top factors',
   re.search(r'_S100-100T60-60(_\d+)?\.gcode$', si['file']) is not None,
   si['file'])
ck('taper: bottom keeps the size, top reaches the top factor '
   '(extruding z-span, hops excluded)',
   abs((sb[1] - sb[0]) - 40.0) < 0.6 and abs((st[1] - st[0]) - 24.0) < 0.6,
   'bottom %.1f top %.1f' % (sb[1] - sb[0], st[1] - st[0]))
ck('taper: E drops with the removed material (recomputed per move)',
   esum(tap) < esum(src) * 0.93, '%.0f vs %.0f' % (esum(tap), esum(src)))
ck('taper: travel golden rule holds (0 flat ink crossings)',
   len(audit(tap)) == 0, str(audit(tap)[:2]))

uni, siu = pp.apply_scale(src, sx=1.2, sy=1.2,
                          out_dir=os.path.join(d, 'Scale'))
su = span_at(uni, zt)
ck('uniform scale stays untouched (no T in the filename, top = 120%)',
   re.search(r'_S120-120\.gcode$', siu['file']) is not None
   and not siu['taper']
   and abs((su[1] - su[0]) - 48.0) < 0.6, siu['file'])

grow, _ = pp.apply_scale(src, sx=1.0, sy=1.0, sxt=1.5, syt=1.5,
                         out_dir=os.path.join(d, 'Scale'))
sg = span_at(grow, zt)
ck('taper > 100%% grows the top', (sg[1] - sg[0]) > 55.0,
   'top %.1f' % (sg[1] - sg[0]))
try:
    pp.apply_scale(src, sx=1.0, sy=1.0, out_dir=os.path.join(d, 'Scale'))
    bad = False
except ValueError:
    bad = True
ck('engine: 100/100 without a taper still refuses', bad, '')
try:
    pp.apply_scale(src, sx=5.0, sy=1.0, out_dir=os.path.join(d, 'Scale'))
    bad = False
except ValueError:
    bad = True
ck('engine: out-of-range scale refuses (25..300%%)', bad, '')
try:
    pp.apply_scale(src, sx=1.0, sy=1.0, sxt=0.1, syt=None,
                   out_dir=os.path.join(d, 'Scale'))
    bad = False
except ValueError:
    bad = True
ck('engine: out-of-range TOP factor refuses', bad, '')

# ---------------- engine: twist ----------------------------------------------
tw, ti = pp.apply_twist(src, deg=90.0, out_dir=os.path.join(d, 'Twist'))
ck('twist: filename carries the angle, lands in Twist/',
   re.search(r'_TWR90(_\d+)?\.gcode$', ti['file']) is not None
   and os.path.basename(os.path.dirname(tw)) == 'Twist', ti['file'])
ck('twist: E stays verbatim (rotation is isometric)',
   abs(esum(tw) - esum(src)) < 0.02,
   '%.3f vs %.3f' % (esum(tw), esum(src)))
b = wall_points_at(tw, 0.28)
t = wall_points_at(tw, zt)
ang = math.radians(90.0)
cx = cy = 110.0
ca, sa = math.cos(ang), math.sin(ang)
mx = 0.0
for (px, py) in b:
    ex = cx + (px - cx) * ca - (py - cy) * sa
    ey = cy + (px - cx) * sa + (py - cy) * ca
    mx = max(mx, min(math.hypot(ex - tx2, ey - ty2) for (tx2, ty2) in t))
ck('twist: the top wall polygon IS the bottom polygon rotated 90 deg',
   mx < 0.01, 'max deviation %.4fmm' % mx)
ck('twist: travel golden rule holds (0 flat ink crossings)',
   len(audit(tw)) == 0, str(audit(tw)[:2]))

tw2, _ = pp.apply_twist(tap, deg=-45.0, out_dir=os.path.join(d, 'Twist'))
ck('twist after scale (taper + twist combined) works, E still isometric '
   'to the tapered file',
   re.search(r'_TWR-45\.gcode$|_TWR45\.gcode$', os.path.basename(tw2))
   is not None
   and abs(esum(tw2) - esum(tap)) < 0.02, os.path.basename(tw2))

for bad_deg in (0.0, 800.0, 0.2):
    try:
        pp.apply_twist(src, deg=bad_deg, out_dir=os.path.join(d, 'Twist'))
        ok_deg = False
    except ValueError:
        ok_deg = True
    if not ok_deg:
        break
ck('engine: twist deg 0 / >720 / <0.5 refuse', ok_deg, '')

print()
if FAIL:
    print('RESULT: FAIL - %d of %d checks failed'
          % (len(FAIL), len(FAIL) + len(PASS)))
    sys.exit(1)
print('RESULT: PASS - %d checks, taper + twist fully pinned' % len(PASS))
