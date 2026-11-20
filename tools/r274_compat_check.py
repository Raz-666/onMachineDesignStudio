#!/usr/bin/env python3
"""R274 field check: MACHINE-MODEL COMPATIBILITY (J7) - synthetic
foreign printers against the portability contract, measured.

COMPATIBILITY.md states the three-layer model (dynamic / defaults /
hardware) - status of release .81. Since then the generator park grew
(textures R265-R266, stencil R267, molds R270-R273) and the R217
matrix never saw them. This battery closes the gap OFFLINE:

  A  config layer: _bed_limits() + _nozzle_diameter() against
     SYNTHETIC printer.cfg / r2_hardware.cfg files - _R2_CONFIG bed
     wins, hardware profile overrides, Ender-3 fallback + hint,
     insane values refused, legacy [r2_postproc] warned-but-read,
     nozzle parsed + clamped
  B  the NEW generators on foreign beds: make_mold + make_mold_blank
     on 180/250/300mm beds - every emitted X/Y inside the bed (the
     I10 clamp proof), honest refusals when the block does not fit,
     nozzle scaling (wall E/mm follows max(0.4, nozzle*1.08))
  C  texture + stencil (the other post-R217 park) on foreign beds
  D  the machine-model MACRO math, rendered with Jinja against
     synthetic printer states: _PRIME_LINE's probe-safe window on
     four machines (home / 300x300 CoreXY with +60/+10 probe / no
     probe / no _R2_CONFIG), PRINT_END presentation clamped to low
     axes
  E  docs parity: COMPATIBILITY.md + MASTER-TODO carry the R274
     status and the new generators
"""
import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_postproc as pp                                   # noqa: E402

try:
    import jinja2
except ImportError:                                       # noqa: E402
    jinja2 = None

try:
    from PIL import Image
except ImportError:                                       # noqa: E402
    Image = None

fails = 0
count = 0


def check(name, ok, info=''):
    global fails, count
    count += 1
    print(('  ok   ' if ok else '  FAIL ') + name)
    if not ok:
        fails += 1
        print('      -> %s' % str(info)[:240])


def medallion_src(d, dia=40.0, thick=8.0, name='med.gcode'):
    """Silhouette reference (contours only) - the r273 recipe."""
    import math
    src = os.path.join(d, name)
    with open(src, 'w') as f:
        f.write(';TYPE:Outer wall\nM82\nG90\n')
        e = 0.0
        for li in range(1, int(thick / 0.2) + 1):
            z = round(li * 0.2, 3)
            pts = [(50.0 + dia / 2 * math.cos(a),
                    50.0 + dia / 2 * math.sin(a))
                   for a in [i * math.pi / 36.0 for i in range(73)]]
            f.write(';LAYER_CHANGE\nG1 Z%.3f F600\n' % z)
            px, py = pts[0]
            f.write('G0 X%.3f Y%.3f F3000\n' % (px, py))
            for (qx, qy) in pts[1:]:
                dxy = math.hypot(qx - px, qy - py)
                e += dxy * 0.05
                f.write('G1 X%.3f Y%.3f E%.5f F1200\n' % (qx, qy, e))
                px, py = qx, qy
    return src


def xy_range(path):
    """(min_x, max_x, min_y, max_y) over all G0/G1 X/Y values."""
    rx = re.compile(r'^G[01] .*[XY]')
    fx = re.compile(r'\bX(-?\d+\.?\d*)')
    fy = re.compile(r'\bY(-?\d+\.?\d*)')
    xs, ys = [], []
    for ln in open(path, errors='replace'):
        code = ln.split(';', 1)[0]
        if code.startswith(('G0 ', 'G1 ')) and ('X' in code or 'Y' in code):
            for m in fx.findall(code):
                xs.append(float(m))
            for m in fy.findall(code):
                ys.append(float(m))
    if not xs or not ys:
        return None
    return (min(xs), max(xs), min(ys), max(ys))


def in_bed(path, bed, tol=3.0):
    r = xy_range(path)
    if r is None:
        return False, 'no moves'
    x0, y0, x1, y1 = bed          # (min_x, min_y, max_x, max_y)
    ok = (r[0] >= x0 - tol and r[1] <= x1 + tol
          and r[2] >= y0 - tol and r[3] <= y1 + tol)
    return ok, (round(r[0], 1), round(r[1], 1),
                round(r[2], 1), round(r[3], 1))


def epmm_seg(path):
    """E per mm per APPLY_TYPE segment - {type: (e_per_mm, dist)}.

    The nozzle invariant is honest PER SEGMENT: walls and brim scale
    their E/mm with max(0.4, nozzle*1.08); the solid hatch instead
    snaps its line COUNT to the region width (n = ceil(w/wid)), so its
    spacing - and with it E/mm - adapts and must NOT be held to the
    2x ratio (measured: 1.65 at 0.4 -> 0.8, correct behavior).
    """
    import math as _m
    segs = {}
    cur = 'HEAD'
    px = py = pe = None
    for ln in open(path, errors='replace'):
        if ln.startswith('APPLY_TYPE'):
            cur = ln.split('TYPE=')[1].strip() if 'TYPE=' in ln else cur
            continue
        code = ln.split(';', 1)[0].strip()
        if not code.startswith(('G0 ', 'G1 ')):
            continue
        parts = code.split()
        p = {}
        for t in parts[1:]:
            if t[0] in 'XYZE' and len(t) > 1:
                try:
                    p[t[0]] = float(t[1:])
                except ValueError:
                    pass
        if 'X' not in p and 'Y' not in p:
            continue
        x = p.get('X', px if px is not None else 0.0)
        y = p.get('Y', py if py is not None else 0.0)
        e = p.get('E', pe if pe is not None else 0.0)
        if px is not None and 'E' in p and e > pe:
            d = _m.hypot(x - px, y - py)
            if d > 0.01:
                sv = segs.setdefault(cur, [0.0, 0.0])
                sv[0] += (e - pe)
                sv[1] += d
        px, py, pe = x, y, e
    return {k: (v[0] / v[1] if v[1] else 0.0, v[1]) for k, v in segs.items()}


def write_cfg(d, name, body):
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, 'w') as f:
        f.write(body)
    return p


R2CFG = """[gcode_macro _R2_CONFIG]
variable_bed_min_x: %.1f
variable_bed_max_x: %.1f
variable_bed_min_y: %.1f
variable_bed_max_y: %.1f
gcode:
"""


def macro_body(cfg_path, macro):
    """gcode: body of [gcode_macro <macro>] (dedented).

    The section header is followed by option lines (description:, ...),
    THEN 'gcode:' - the body is the 4-space-indented block after it.
    """
    want = '[gcode_macro %s]' % macro
    lines = open(cfg_path, errors='replace').read().split('\n')
    on = False
    in_g = False
    body = []
    for ln in lines:
        s = ln.strip()
        if s.startswith('[') and s.endswith(']'):
            if in_g:
                break
            on = (s == want)
            continue
        if not on:
            continue
        if not in_g:
            if s == 'gcode:':
                in_g = True
            continue
        if ln.startswith('    '):
            body.append(ln[4:])
        elif not s:
            body.append('')
        else:
            break
    while body and not body[-1]:
        body.pop()
    return '\n'.join(body)


def render(body, ctx):
    # Klipper's dialect: single-brace {expr} in gcode lines (the same
    # environment macro_render_test uses - double braces would leave
    # {xe|round} literal)
    env = jinja2.Environment(
        loader=jinja2.BaseLoader(),
        variable_start_string='{', variable_end_string='}',
        block_start_string='{%', block_end_string='%}',
        comment_start_string='{#', comment_end_string='#}',
        trim_blocks=True, lstrip_blocks=False)
    return env.from_string(body).render(ctx)


def main():
    D = tempfile.mkdtemp(prefix='r274_')

    print('A  config layer (synthetic printer.cfg)')
    cfg = write_cfg(D, 'a1', R2CFG % (10.0, 260.0, 5.0, 255.0))
    got = pp._bed_limits(cfg)
    check('A1 _R2_CONFIG bed values win',
          got == (10.0, 5.0, 260.0, 255.0), got)
    cfg = write_cfg(D, 'a2', R2CFG % (0.0, 220.0, -3.0, 217.0))
    write_cfg(D, 'r2_hardware.cfg', R2CFG % (10.0, 260.0, 5.0, 255.0))
    got = pp._bed_limits(cfg)
    check('A2 r2_hardware.cfg overrides printer.cfg',
          got == (10.0, 5.0, 260.0, 255.0), got)
    os.remove(os.path.join(D, 'r2_hardware.cfg'))
    buf = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(buf):
        got = pp._bed_limits(write_cfg(D, 'a3', '[stepper_x]\n'))
    check('A3 no config -> Ender-3 default + hint',
          got == (0.0, -3.0, 220.0, 217.0)
          and 'no [gcode_macro _R2_CONFIG]' in buf.getvalue(), got)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        got = pp._bed_limits(write_cfg(
            D, 'a4', R2CFG % (100.0, 50.0, 5.0, 255.0)))
    check('A4 insane values -> default + warning',
          got == (0.0, -3.0, 220.0, 217.0)
          and 'not sane' in buf.getvalue(), got)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        got = pp._bed_limits(write_cfg(
            D, 'a5',
            '[r2_postproc]\nbed_min_x: 0\nbed_max_x: 250\n'
            'bed_min_y: 0\nbed_max_y: 250\n'))
    check('A5 legacy [r2_postproc]: HALTS-KLIPPER warning, values read',
          got == (0.0, 0.0, 250.0, 250.0)
          and 'HALTS KLIPPER' in buf.getvalue(), got)
    got = pp._nozzle_diameter(write_cfg(
        D, 'a6.cfg', '[extruder]\nnozzle_diameter: 0.8\n'))
    check('A6 nozzle_diameter parsed from [extruder]',
          got == (0.8, True), got)
    got = pp._nozzle_diameter(write_cfg(
        D, 'a7.cfg', '[extruder]\nnozzle_diameter: 5.0\n'))
    got2 = pp._nozzle_diameter(write_cfg(D, 'a7b.cfg', '[extruder]\n'))
    check('A7 nozzle clamped to 2.0, missing -> 0.6',
          got == (2.0, True) and got2 == (0.6, False), (got, got2))

    print('B  molds + blanks on foreign beds')
    src = medallion_src(D)
    for tag, bed in (('prusamini-180', (0.0, 0.0, 180.0, 180.0)),
                     ('corexy-300', (0.0, 0.0, 300.0, 300.0))):
        Bd = tempfile.mkdtemp(prefix='r274b_')
        out, i = pp.make_mold(src, wall=5.0, part='TOP', plane='OFF',
                              z_off=0.0, bed=bed, out_dir=Bd)
        ok, r = in_bed(out, bed)
        check('B1 make_mold on %s bed: every XY inside' % tag, ok, r)
    Bd = tempfile.mkdtemp(prefix='r274b_')
    out, i = pp.make_mold_blank(shape='BAR', length=90.0, bar_w=40.0,
                                bar_h=25.0, wall=5.0,
                                bed=(0.0, 0.0, 250.0, 250.0), out_dir=Bd)
    ok, r = in_bed(out, (0.0, 0.0, 250.0, 250.0))
    check('B2 make_mold_blank BAR on 250mm bed: inside', ok, r)
    try:
        pp.make_mold_blank(shape='PLAQUE', width=150.0, height=110.0,
                           thick=6.0, wall=5.0,
                           bed=(0.0, 0.0, 120.0, 120.0),
                           out_dir=tempfile.mkdtemp(prefix='r274b_'))
        check('B3 oversized plaque refused on 120mm bed', False, 'built')
    except ValueError as ex:
        check('B3 oversized plaque refused on 120mm bed',
              'bed' in str(ex) or 'needs' in str(ex), str(ex)[:120])
    try:
        # wall clamps at 15mm - force the refusal with a BIG source
        # (dia 100 + 2x15 wall = 130mm block vs 108mm usable bed)
        pp.make_mold(medallion_src(D, dia=100.0, name='big.gcode'),
                     wall=15.0, part='TOP', plane='OFF', z_off=0.0,
                     bed=(0.0, 0.0, 120.0, 120.0),
                     out_dir=tempfile.mkdtemp(prefix='r274b_'))
        check('B4 mold block vs tiny bed refused', False, 'built')
    except ValueError as ex:
        check('B4 mold block vs tiny bed refused',
              'mold block needs' in str(ex), str(ex)[:120])
    D4d = tempfile.mkdtemp(prefix='r274b_')
    D8d = tempfile.mkdtemp(prefix='r274b_')
    o4 = pp.make_mold(src, wall=5.0, part='TOP', plane='OFF', z_off=0.0,
                      nozzle=0.4, bed=(0.0, 0.0, 250.0, 250.0),
                      out_dir=D4d)[0]
    o8 = pp.make_mold(src, wall=5.0, part='TOP', plane='OFF', z_off=0.0,
                      nozzle=0.8, bed=(0.0, 0.0, 250.0, 250.0),
                      out_dir=D8d)[0]
    s4 = epmm_seg(o4)
    s8 = epmm_seg(o8)
    ratios = {}
    for seg in ('WALL-OUTER', 'BRIM'):
        a = s4.get(seg, (0.0, 0.0))[0]
        b = s8.get(seg, (0.0, 0.0))[0]
        ratios[seg] = (b / a) if a else 0.0
    check('B5 nozzle scaling: WALL-OUTER + BRIM E/mm follow nozzle*1.08',
          all(1.85 <= r <= 2.35 for r in ratios.values()),
          {k: round(v, 3) for k, v in ratios.items()})
    r4 = xy_range(o4)
    r8 = xy_range(o8)
    check('B6 nozzle does not move the block (placement stable)',
          r4 and r8 and abs(r4[0] - r8[0]) <= 2.0
          and abs(r4[1] - r8[1]) <= 2.0 and abs(r4[2] - r8[2]) <= 2.0
          and abs(r4[3] - r8[3]) <= 2.0, (r4, r8))

    print('C  texture + stencil on foreign beds')
    try:
        import r2_texture as tex
        tdir = tempfile.mkdtemp(prefix='r274c_')
        tsrc = os.path.join(tdir, 't.gcode')
        with open(tsrc, 'w') as f:
            f.write(open(src).read())
        tout, ti = tex.apply_texture(tsrc, out_dir=tdir, mode='BUMPS',
                                     bump_pattern='GRID', bump_scale=10.0,
                                     bump_amp=0.35, bed=(0.0, 0.0, 250.0,
                                                         250.0))
        ok, r = in_bed(tout, (0.0, 0.0, 250.0, 250.0))
        check('C1 apply_texture on 250mm bed: inside', ok, r)
    except ImportError:
        check('C1 apply_texture on 250mm bed: inside', False,
              'r2_texture not importable')
    if Image is None:
        check('C2 stencil on 250mm bed: inside', False, 'PIL missing')
    else:
        sdir = tempfile.mkdtemp(prefix='r274c_')
        png = os.path.join(sdir, 's.png')
        Image.new('L', (64, 64), 128).save(png)
        out, si = pp.make_stencil(png, steps=2, size_mm=60.0,
                                  bed=(0.0, 0.0, 250.0, 250.0),
                                  out_dir=sdir)
        ok, r = in_bed(out, (0.0, 0.0, 250.0, 250.0))
        check('C2 stencil on 250mm bed: inside', ok, r)

    print('D  machine-model macro math (Jinja, synthetic printers)')
    if jinja2 is None:
        check('D1-D6 macro math', False, 'jinja2 missing')
    else:
        pl = macro_body(os.path.join(os.path.dirname(HERE), 'macros',
                                     '08_print_start_stop.cfg'),
                        '_PRIME_LINE')
        cases = (
            ('home 244x238, probe -45/-10',
             {'gcode_macro _R2_CONFIG': {'bed_min_x': 0.0,
                                         'bed_max_x': 244.0,
                                         'bed_min_y': -3.0,
                                         'bed_max_y': 238.0}},
             {'probe': {'x_offset': -45.0, 'y_offset': -10.0}},
             (0.0, -3.0, 244.0, 238.0)),
            ('corexy 300x300, probe +60/+10',
             {'gcode_macro _R2_CONFIG': {'bed_min_x': 0.0,
                                         'bed_max_x': 300.0,
                                         'bed_min_y': 0.0,
                                         'bed_max_y': 300.0}},
             {'probe': {'x_offset': 60.0, 'y_offset': 10.0}},
             (0.0, 0.0, 300.0, 300.0)),
            ('ender 220, NO probe',
             {'gcode_macro _R2_CONFIG': {'bed_min_x': 0.0,
                                         'bed_max_x': 220.0,
                                         'bed_min_y': -3.0,
                                         'bed_max_y': 217.0}},
             {}, (0.0, -3.0, 220.0, 217.0)),
            ('NO _R2_CONFIG (defaults), probe -45/-10',
             {}, {'probe': {'x_offset': -45.0, 'y_offset': -10.0}},
             (0.0, -3.0, 220.0, 217.0)),
        )
        for idx, (tag, r2cfg, settings, bed) in enumerate(cases):
            printer = {'configfile': {'settings': settings}}
            if r2cfg:
                printer['gcode_macro _R2_CONFIG'] = r2cfg
            txt = render(pl, {'printer': printer, 'params': {}})
            m = re.search(r'Prime line X(-?[\d.]+)-(-?[\d.]+) Y(-?[\d.]+)',
                          txt)
            if not m:
                check('D%d _PRIME_LINE window on %s' % (idx + 1, tag),
                      False, txt[:160])
                continue
            xe, xs, y = float(m.group(1)), float(m.group(2)), \
                float(m.group(3))
            bx0, by0, bx1, by1 = bed
            px = settings.get('probe', {}).get('x_offset', 0.0)
            py = settings.get('probe', {}).get('y_offset', 0.0)
            xmin = max(bx0, bx0 - px) + 5
            xmax = min(bx1, bx1 - px) - 5
            ymin = max(by0, by0 - py) + 5
            ymax = min(by1, by1 - py) - 5
            gx = [float(v) for v in
                  re.findall(r'^G[01] X(-?[\d.]+)', txt, re.M)]
            gy = [float(v) for v in
                  re.findall(r'^G[01] .*?Y(-?[\d.]+)', txt, re.M)]
            ok = (xmin - 0.5 <= xe <= xs <= xmax + 0.5
                  and ymin - 0.5 <= y <= ymax + 0.5
                  and all(xmin - 0.5 <= v <= xmax + 0.5 for v in gx)
                  and all(ymin - 0.5 <= v <= ymax + 0.5 for v in gy)
                  and bx0 <= xe + px <= bx1 and by0 <= y + py <= by1)
            check('D%d _PRIME_LINE probe-safe window on %s'
                  % (idx + 1, tag), ok,
                  (xe, xs, round(y, 1), 'window',
                   round(xmin, 1), round(xmax, 1),
                   round(ymin, 1), round(ymax, 1)))
        pe = macro_body(os.path.join(os.path.dirname(HERE), 'macros',
                                     '08_print_start_stop.cfg'),
                        'PRINT_END')
        printer = {
            'gcode_macro _STATE': {'end_guard': False},
            'save_variables': {'variables': {}},
            'print_stats': {'state': 'complete', 'print_duration': 0.0,
                            'filament_used': 0.0, 'total_duration': 0.0,
                            'info': {}},
            'extruder': {'pressure_advance': 0.05},
            'gcode_macro _R2_CONFIG': {'present_x': 10, 'present_y': 228},
            'toolhead': {'homed_axes': 'xyz',
                         'axis_maximum': {'x': 244.0, 'y': 238.0,
                                          'z': 180.0},
                         'axis_minimum': {'x': 0.0, 'y': -3.0, 'z': 0.0}},
            'gcode_move': {'gcode_position': {'z': 170.0, 'x': 100.0,
                                              'y': 100.0, 'e': 0.0}},
            'configfile': {'settings': {}},
        }
        txt = render(pe, {'printer': printer, 'params': {}})
        mz = re.search(r'^\s*G0 Z([\d.]+) F600', txt, re.M)
        ok = mz and float(mz.group(1)) <= 178.0
        check('D5 PRINT_END lift clamped on a low-Z machine (180)',
              ok, mz and mz.group(1))
        printer['toolhead']['axis_maximum'].update({'x': 150.0, 'y': 150.0})
        printer['toolhead']['axis_minimum'].update({'x': 0.0, 'y': 0.0})
        txt = render(pe, {'printer': printer, 'params': {}})
        mp = re.search(r'^\s*G0 X(\d+) Y(\d+) F6000', txt, re.M)
        ok = mp and int(mp.group(2)) <= 146 and int(mp.group(1)) >= 2
        check('D6 PRINT_END presentation clamped on 150mm axes',
              ok, mp and (mp.group(1), mp.group(2)))

    print('E  docs parity')
    comp = open(os.path.join(os.path.dirname(HERE), 'COMPATIBILITY.md'),
                encoding='utf-8').read()
    check('E1 COMPATIBILITY.md carries the R274 status + new generators',
          'R274' in comp and 'make_mold' in comp and 'stencil' in comp
          and 'texture' in comp)
    mt = open(os.path.join(os.path.dirname(HERE), 'docs-notes',
                           'MASTER-TODO.md'), encoding='utf-8').read()
    check('E2 MASTER-TODO J7 carries the R274 STAND',
          'STAND R274' in mt)

    print()
    print('%d/%d checks passed' % (count - fails, count))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
