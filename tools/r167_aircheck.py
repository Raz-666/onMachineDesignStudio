#!/usr/bin/env python3
"""R167: geometry-reality audit - measure what the generators actually build.

WHY (field log .125): the backplate NEVER fit - 'not a single one, all too
big, 1mm one way, almost 2mm the other'. The code comment said '0.3mm play
per side' but the wall lines print with their CENTER on the contour: the
shaft's light size is photo - wid, the plate's outer size is plate + wid.
Nobody measured. This tool measures - from the GCODE, the way a caliper
would - and fails the build when the fit or the support rule drifts:

  1. FRAME FIT     backplate outer size vs photo-shaft light size,
                   measured from the extrusion coordinates: 0.15..0.60mm
                   play per side (clicks behind the nubs, no force fit)
  2. AIR SCAN      every sampled extrusion point from layer 2 on must sit
                   on material one layer below within the 45-degree cone
                   (layer_h * 1.3). Declared BRIDGE sections are exempt -
                   the shelf over the groove is a wanted, slow bridge
  3. M204 THRIFT   generated files must not storm M204 (the .125
                   Timer-too-close chain): at least 8 moves per M204

Run:  python3 tools/r167_aircheck.py     (from the repo root)
"""
import importlib.util
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location(
    'pp', os.path.join(HERE, 'r2_postproc.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

fails = []
warns = []
runs = 0


def check(name, ok, info=''):
    global runs
    runs += 1
    print('%s %-52s %s' % ('OK  ' if ok else 'FAIL', name, info))
    if not ok:
        fails.append((name, info))


G0 = re.compile(r'^G0 X([-\d.]+) Y([-\d.]+)')
G1 = re.compile(r'^G1 X([-\d.]+) Y([-\d.]+) E([\d.]+)')


class Scan:
    """object-split extrusion sampler with layer + TYPE tracking"""

    def __init__(self):
        self.layers = {}      # (obj, layer) -> pts (incl. bridges: support)
        self.check = {}       # (obj, layer) -> pts to CHECK (no bridges)
        self.x = self.y = 0.0
        self.layer = 0
        self.obj = None
        self.type = ''
        self.m204 = 0
        self.moves = 0

    def feed(self, txt):
        for ln in txt.splitlines():
            if ln.startswith('<<<NEWFILE>>>'):
                self.layer = 0
                self.obj = None
                continue
            if ln.startswith(';LAYER_CHANGE'):
                self.layer += 1
                continue
            if ln.startswith(';TYPE:'):
                self.type = ln[6:].strip().upper()
                continue
            if ln.startswith('M204'):
                self.m204 += 1
                continue
            m = G0.match(ln)
            if m:
                self.x, self.y = float(m.group(1)), float(m.group(2))
                continue
            m = G1.match(ln)
            if m:
                self.moves += 1
                nx, ny, e = (float(m.group(1)), float(m.group(2)),
                             float(m.group(3)))
                if e > 0 and self.obj is not None:
                    d = math.hypot(nx - self.x, ny - self.y)
                    n = max(1, int(d / 0.4))
                    key = (self.obj, self.layer)
                    pts = [(self.x + (nx - self.x) * i / n,
                            self.y + (ny - self.y) * i / n)
                           for i in range(n + 1)]
                    self.layers.setdefault(key, []).extend(pts)
                    if self.type != 'BRIDGE':
                        # declared bridges may CARRY the layer above, they
                        # just do not have to BE carried themselves
                        self.check.setdefault(key, []).extend(pts)
                self.x, self.y = nx, ny
                continue
            if ln.startswith('EXCLUDE_OBJECT_START'):
                self.obj = ln.split('NAME=')[1].strip()
            elif ln.startswith('EXCLUDE_OBJECT_END'):
                self.obj = None

    def air(self):
        """layer-2+ points without 45-deg support below -> [(layer, n)]"""
        grid = 0.6
        cell = 1.0 / grid
        rad = int(math.ceil(0.26 * 1.3 / grid)) + 1
        by_layer = {}
        for (obj, li), ps in self.check.items():
            by_layer.setdefault(li, []).extend(ps)
        bad = []
        for li in sorted(by_layer):
            below = set()
            for (obj2, li2), ps in self.layers.items():
                if li2 == li - 1:
                    below.update((int(px * cell), int(py * cell))
                                 for (px, py) in ps)
            if not below:
                continue
            n = 0
            for (px, py) in by_layer[li]:
                gx, gy = int(px * cell), int(py * cell)
                ok = False
                for dx in range(-rad, rad + 1):
                    for dy in range(-rad, rad + 1):
                        if (dx * dx + dy * dy <= rad * rad
                                and (gx + dx, gy + dy) in below):
                            ok = True
                            break
                    if ok:
                        break
                if not ok:
                    n += 1
            if n:
                bad.append((li, n))
        return bad


# ---- 1+2: frame fit + air scan ------------------------------------------------
d = tempfile.mkdtemp(prefix='r167f_')
try:
    out, info = pp.make_frame(preset='10x15', depth=8, frame_w=10, corner=4,
                              closure='BACK', out_dir=d)
    files = sorted(f for f in os.listdir(d) if f.endswith('.gcode'))
    sc = Scan()
    for f in files:
        sc.feed('<<<NEWFILE>>>\n' + open(os.path.join(d, f)).read())

    # fit: plate outer vs shaft light, measured from the coordinates
    plate = [p for (o, l), ps in sc.layers.items()
             if 'PLATE' in o.upper() or 'BACK' in o.upper() for p in ps]
    frame = [p for (o, l), ps in sc.layers.items() if o == 'FRAME'
             for p in ps]
    m = re.search(r'LINE_WIDTH=([\d.]+)',
                  open(os.path.join(d, files[0])).read())
    wid = float(m.group(1))
    plate_w = (max(p[0] for p in plate) - min(p[0] for p in plate)) + wid
    plate_h = (max(p[1] for p in plate) - min(p[1] for p in plate)) + wid

    def wall_center(vals, lo, hi):
        sel = sorted(v for v in vals if lo < v < hi)
        best, bi = -1, 0
        i = 0
        for j in range(len(sel)):
            while sel[j] - sel[i] > 0.3:
                i += 1
            if j - i > best:
                best, bi = j - i, i
        return sum(sel[bi:bi + best + 1]) / (best + 1)

    fx = [p[0] for p in frame]
    fy = [p[1] for p in frame]
    fcx, fcy = (min(fx) + max(fx)) / 2, (min(fy) + max(fy)) / 2
    r_w = wall_center(fx, fcx + 30, max(fx) - 2)
    l_w = wall_center(fx, min(fx) + 2, fcx - 30)
    t_w = wall_center(fy, fcy + 30, max(fy) - 2)
    b_w = wall_center(fy, min(fy) + 2, fcy - 30)
    shaft_w = (r_w - wid / 2) - (l_w + wid / 2)
    shaft_h = (t_w - wid / 2) - (b_w + wid / 2)
    fit_x = (shaft_w - plate_w) / 2
    fit_y = (shaft_h - plate_h) / 2
    check('frame fit: plate vs shaft (photo wall light size)',
          0.15 <= fit_x <= 0.60 and 0.15 <= fit_y <= 0.60,
          'X %+.2f Y %+.2f mm/side' % (fit_x, fit_y))

    bad = sc.air()
    check('frame air scan: no floating extrusion (45-deg rule, bridges ok)',
          not bad, str(bad[:3]))
    check('frame M204 thrift (>= 8 moves per M204)',
          sc.moves >= 8 * max(1, sc.m204), '%d moves / %d M204'
          % (sc.moves, sc.m204))
finally:
    import shutil
    shutil.rmtree(d, ignore_errors=True)

# ---- litho: air scan + thrift on the reference photo -------------------------
d = tempfile.mkdtemp(prefix='r167l_')
try:
    src = os.path.join(ROOT, '..', 'uploads', 'Bun2.jpg')
    if not os.path.isfile(src):
        src = '/home/user/uploads/Bun2.jpg'
    out, info = pp.make_lithophane(
        src, height_mm=50.0, layer_h=0.12, levels=0, frame=True,
        brim_loops=6, ironing=False, orient='FLAT', colors=1, col_layers=0,
        border=0.0, corner_r=0.0, col_mode='OFF', contrast=True,
        material='PLA', bed=(0.0, -3.0, 244.0, 238.0), nozzle=0.6,
        out_dir=d, version=1)
    sc = Scan()
    sc.feed(open(out).read())
    bad = sc.air()
    check('litho FLAT air scan: step walls sit on the step below (45 deg)',
          not bad, str(bad[:3]))
    check('litho M204 thrift (>= 3 moves per M204 - photos have '
          'many scattered blocks)',
          sc.moves >= 3 * max(1, sc.m204), '%d moves / %d M204'
          % (sc.moves, sc.m204))
    txt = open(out).read()
    check('litho step walls present (Outer wall blocks per step layer)',
          txt.count(';TYPE:Outer wall') >= 12, str(txt.count(';TYPE:Outer wall')))
finally:
    import shutil
    shutil.rmtree(d, ignore_errors=True)

print('==== R167 AIRCHECK: %d checks, %d FAIL, %d warn ===='
      % (runs, len(fails), len(warns)))
for (n, i) in fails:
    print('FAIL %s %s' % (n, i))
sys.exit(1 if fails else 0)
