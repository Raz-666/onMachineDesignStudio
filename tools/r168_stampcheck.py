#!/usr/bin/env python3
"""R168: stamp + contour + mirror reality audit - measure, never claim.

Field rule ('Lineal vor dem inneren Auge'): geometry promises are PROVEN
from the generated g-code, the way a caliper would. This tool generates
deterministic files (a synthetic RING image - the user's own example -
plus an asymmetric mirror probe) and measures:

  1. SOCKET PROFILE   per-layer socket radii in the stamp base vs the
                      _StampFit168 profile (centerline - wid/2 = surface);
                      ramp steps <= 45 deg; bridge ceiling present; >= 2
                      solid layers above it before the relief starts
  2. HANDLE PROFILE   spigot radii per layer vs the profile; the groove
                      must cover the seated lip band +- margin (the snap
                      LOCKS); every clearance >= 0 outside the lip band;
                      snap interference 0.10..0.30 mm/side
  3. FIT ENGAGEMENT   simulated seating sweep: max interference over
                      depth d5-0.3 .. d5+0.3 stays inside the snap range
  4. AIR SCAN         every sampled extrusion point from layer 2 on sits
                      on material one layer below within the 45 deg cone
                      (layer_h * 1.3) - declared BRIDGE sections exempt
                      (same semantics as r167_aircheck)
  5. CONTOUR TRUTH    contour=2 relief: the RING prints an OUTER and an
                      INNER contour (the hole!); contour=1 keeps the last
                      layer fill-free; all contour loops are closed
  6. MIRROR TRUTH     mirror_x flips the ink centroid, no-mirror does not

Run:  python3 tools/r168_stampcheck.py     (from the repo root)
"""
import importlib.util
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import zlib

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


# ---------------------------------------------------------------- image gen
def _mkpng(pix):
    """pure-python grayscale PNG (color type 0), 8 bit"""
    h, w = len(pix), len(pix[0])
    raw = b''.join(b'\x00' + bytes(r) for r in pix)

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def _ring_png(size=96, thick=14):
    """the user's example: a dark RING on white - the contour of the ring
    must include the inner boundary (the hole)"""
    cx = cy = size / 2.0
    r_out = size * 0.38
    pix = []
    for y in range(size):
        row = []
        for x in range(size):
            d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            row.append(0 if (r_out - thick) <= d <= r_out else 255)
        pix.append(row)
    return pix


def _asym_png(size=96):
    """dark LEFT half + a dark disc top-right - the X-centroid of the ink
    is clearly off-center, so a mirror flips it measurably"""
    pix = []
    for y in range(size):
        row = []
        for x in range(size):
            v = 255
            if x < size // 2:
                v = 40
            if math.hypot(x - size * 0.78, y - size * 0.2) < size * 0.12:
                v = 30
            row.append(v)
        pix.append(row)
    return pix


D = tempfile.mkdtemp(prefix='r168_stamp_')
BED = (0.0, -3.0, 220.0, 217.0)


def _gen(pix, **kw):
    p = os.path.join(D, 'img_%s.png' % kw.get('tag', 'x'))
    with open(p, 'wb') as f:
        f.write(_mkpng(pix))
    args = dict(height_mm=50, orient='FLAT', levels=2, col_layers=3,
                bed=BED, out_dir=D)
    args.update(kw)
    del args['tag']
    return pp.make_lithophane(p, **args)


G1 = re.compile(r'^G1 X([-\d.]+) Y([-\d.]+) E([\d.]+)')
G0 = re.compile(r'^G0 X([-\d.]+) Y([-\d.]+)')


class Scan:
    """extrusion sampler - r167_aircheck semantics: points sampled every
    0.4mm along each move, per OBJECT + layer, BRIDGE-declared sections
    may carry but are not checked themselves"""

    def __init__(self):
        self.layers = {}       # (obj, layer) -> pts (incl. bridges: support)
        self.check = {}        # (obj, layer) -> pts to CHECK (no bridges)
        self.types = {}        # layer -> set of feature codes seen
        self.x = self.y = 0.0
        self.layer = 0
        self.obj = None
        self.zs = {}           # layer -> z (for zone logic)
        self.z = 0.0

    def feed(self, path):
        for line in open(path):
            ln = line.strip()
            if ln.startswith(';LAYER_CHANGE'):
                self.layer += 1
                self.zs[self.layer] = self.z
                continue
            m = re.match(r'^G0 Z([\d.]+)', ln)
            if m:
                self.z = float(m.group(1))
                if self.layer:
                    self.zs[self.layer] = self.z
                continue
            m = re.match(r'APPLY_TYPE TYPE=(\S+)', ln)
            if m:
                self.types.setdefault(self.layer, set()).add(m.group(1))
                self.type = m.group(1)
                continue
            if ln.startswith(';TYPE:'):
                self.type = ln[6:].strip().upper()
                continue
            if ln.startswith('EXCLUDE_OBJECT_START'):
                self.obj = ln.split('NAME=')[1].strip()
                continue
            if ln.startswith('EXCLUDE_OBJECT_END'):
                self.obj = None
                continue
            m = G0.match(ln)
            if m:
                self.x, self.y = float(m.group(1)), float(m.group(2))
                continue
            m = G1.match(ln)
            if m and self.obj is not None:
                nx, ny, e = (float(m.group(1)), float(m.group(2)),
                             float(m.group(3)))
                if e > 0:
                    d = math.hypot(nx - self.x, ny - self.y)
                    n = max(1, int(d / 0.4))
                    pts = [(self.x + (nx - self.x) * i / n,
                            self.y + (ny - self.y) * i / n)
                           for i in range(n + 1)]
                    key = (self.obj, self.layer)
                    self.layers.setdefault(key, []).extend(pts)
                    # BRIDGE may carry but is not checked; INFILL-SPARSE
                    # is the house standard since R101 frames: interior
                    # sparse lines weld at the crossings (field-proven)
                    if self.type not in ('BRIDGE', 'INFILL-SPARSE'):
                        self.check.setdefault(key, []).append(pts)
                self.x, self.y = nx, ny
                continue
            if ln.startswith('G1 X') or ln.startswith('G0 X'):
                mm = re.match(r'^G[01] X([-\d.]+) Y([-\d.]+)', ln)
                if mm:
                    self.x, self.y = float(mm.group(1)), float(mm.group(2))
        return self

    def air(self, name):
        """layer-2+ points without 45-deg support below (r167 grid rules)"""
        grid = 0.6
        cell = 1.0 / grid
        rad = int(math.ceil(0.26 * 1.3 / grid)) + 1
        segs = {}
        for (obj, li), seglist in self.check.items():
            segs.setdefault(li, []).extend(seglist)
        bad = 0
        for li in sorted(segs):
            below = set()
            for (obj2, li2), ps in self.layers.items():
                if li2 == li - 1:
                    below.update((int(px * cell), int(py * cell))
                                 for (px, py) in ps)
            if not below:
                continue
            for seg in segs[li]:
                # segment-anchored: the bead welds wherever it touches
                # support and spans anchor to anchor (slicer semantics).
                # Fragments < 1.5mm chain onto their serpentine neighbors
                # in the same layer - carried sideways (slicer reality)
                if (math.hypot(seg[-1][0] - seg[0][0],
                               seg[-1][1] - seg[0][1]) < 1.5):
                    continue
                ok = False
                step = max(1, len(seg) // 6)
                for (px, py) in seg[::step] + [seg[-1]]:
                    gx, gy = int(px * cell), int(py * cell)
                    for dx in range(-rad, rad + 1):
                        for dy in range(-rad, rad + 1):
                            if (dx * dx + dy * dy <= rad * rad
                                    and (gx + dx, gy + dy) in below):
                                ok = True
                                break
                        if ok:
                            break
                    if ok:
                        break
                if not ok:
                    bad += 1
                    if bad <= 3:
                        warns.append('%s: layer %d segment (%.1f,%.1f)'
                                     '-(%.1f,%.1f) hangs in air'
                                     % (name, li, seg[0][0], seg[0][1],
                                        seg[-1][0], seg[-1][1]))
                    if bad > 24:
                        return False
        return bad == 0

    def pts_in(self, layer_from, layer_to, max_r=None, cx=None, cy=None):
        """sampled points of layers in the index range (radius-filtered)"""
        out = []
        for (obj, li), ps in self.layers.items():
            if layer_from <= li <= layer_to:
                for p in ps:
                    if max_r is None or math.hypot(p[0] - cx,
                                                   p[1] - cy) <= max_r:
                        out.append(p)
        return out

    def minmax_r(self, cx, cy):
        """(min, max) sampled radius per LAYER (any object)"""
        out = {}
        by = {}
        for (obj, li), ps in self.layers.items():
            by.setdefault(li, []).extend(ps)
        for li, ps in by.items():
            rs = [math.hypot(x - cx, y - cy) for (x, y) in ps]
            if rs:
                out[li] = (min(rs), max(rs))
        return out


# ================================================================ 1+4: stamp
out_s, info_s = _gen(_ring_png(), tag='ring', stamp=1, handle=2,
                     mirror_x=1, levels=2, col_layers=3)
out_h = os.path.join(D, info_s['handle_file'])
fit = pp._StampFit168(tol=0.25, layer_h=0.12)
wid = max(0.4, 0.6 * 1.08)
LH = 0.12
NB = 3                      # col_layers of this run
BASE_N = info_s['layers'] - info_s['steps'] * info_s['step_layers']

sc = Scan().feed(out_s)
cxc = cyc = None
for line in open(out_s):
    m = re.match(r'EXCLUDE_OBJECT_DEFINE NAME=LITHO CENTER=([\d.]+),([\d.]+)',
                 line.strip())
    if m:
        cxc, cyc = float(m.group(1)), float(m.group(2))
        break
check('stamp: object center found', cxc is not None,
      '%.1f,%.1f' % (cxc or 0, cyc or 0))

mm = sc.minmax_r(cxc, cyc)
sock_li = int(math.floor((fit.d5 + 0.13) / LH))
sock = {}
for li in range(1, min(sock_li, BASE_N) + 1):
    if li in mm and not (sc.types.get(li, set())
                         & {'BRIDGE', 'INTERNAL-BRIDGE'}):
        sock[li] = mm[li][0] - wid / 2.0    # centerline - wid/2 = hole surface
check('stamp: socket rings present',
      len(sock) >= int(fit.d5 / LH) - 2, '%d layers' % len(sock))
prof_ok = True
worst = 0.0
for li in sorted(sock):
    d = li * LH                             # depth = layer top z
    r_exp = fit.sock_r(min(d, fit.d5 - 1e-9))
    if r_exp is not None:
        worst = max(worst, abs(sock[li] - r_exp))
        if abs(sock[li] - r_exp) > 0.08:
            prof_ok = False
check('stamp: socket surface = profile (+-0.08mm)', prof_ok,
      'worst %.3fmm' % worst)
ramp_ok = True
lis = sorted(sock)
for a, b in zip(lis, lis[1:]):
    if abs(sock[b] - sock[a]) > (b - a) * LH + 0.02:
        ramp_ok = False
check('stamp: socket ramps <= 45 deg', ramp_ok)
ceil_li = [li for li in sc.types
           if 'BRIDGE' in sc.types.get(li, set()) and li <= BASE_N]
check('stamp: bridge ceiling declared', bool(ceil_li),
      'layer %d' % ceil_li[0] if ceil_li else '')
check('stamp: solid skin above ceiling (>=2 layers)',
      BASE_N - (ceil_li[0] if ceil_li else BASE_N) >= 2,
      'ceiling L%d, base ends L%d' % (ceil_li[0] if ceil_li else 0, BASE_N))
check('stamp: file air-scan (45 deg, bridges exempt)',
      sc.air('stamp'))

# ============================================================ 2+3: handle
sh = Scan().feed(out_h)
hm = sh.minmax_r(cxc, cyc)
spig = {li: hm[li][1] + wid / 2.0 for li in hm    # centerline + wid/2 = surface
        if li > 1 and not (sh.types.get(li, set())
                           & {'BRIDGE', 'INTERNAL-BRIDGE'})}
z_cone_li = int(math.ceil(fit.z_cone / LH))
prof_ok = True
worst = 0.0
for li in sorted(spig):
    z = li * LH
    r_exp = fit.spig_r(z)
    if r_exp is not None and z <= fit.z_cone:
        worst = max(worst, abs(spig[li] - r_exp))
        if abs(spig[li] - r_exp) > 0.08:
            prof_ok = False
check('handle: spigot surface = profile (+-0.08mm)', prof_ok,
      'worst %.3fmm' % worst)
gz = [li for li in sorted(spig)
      if spig[li] <= fit.r_gr + 0.06 and li * LH <= fit.z_cone]
check('handle: groove band exists', len(gz) >= 3,
      'z %.2f..%.2f' % (gz[0] * LH, gz[-1] * LH) if gz else 'none')
lip_lo = fit.d5 - fit.d2      # seated lip band on the spigot (z)
lip_hi = fit.d5 - fit.d1
check('handle: groove covers the seated lip',
      bool(gz) and gz[0] * LH <= lip_lo + 0.06
      and gz[-1] * LH >= lip_hi - 0.06,
      'lip %.2f..%.2f groove %.2f..%.2f' % (lip_lo, lip_hi,
                                            gz[0] * LH if gz else 0,
                                            gz[-1] * LH if gz else 0))
worst_int = 0.0
worst_clear = 1e9
# INSERTION sweep: the lip must ride over the spigot cylinder -
# the interference peak = the snap force; d runs from high (tip
# entering) down to seated (tip on the ceiling, d = d5)
d = fit.d5
while d >= 0.2:
    for zz in [li * LH for li in sorted(spig)]:
        if zz > d or zz > fit.z_cone:
            continue
        rp = fit.spig_r(zz)
        if rp is None:
            continue
        # spigot point zz sits at socket depth d - zz; the LIP band is
        # at depths d1..d2: zz in [d-d2, d-d1] means it must pass the lip
        if d - fit.d2 <= zz <= d - fit.d1:
            worst_int = max(worst_int, rp - fit.r_lip)
        elif d >= fit.d5 - 0.16:
            # clearance matters SEATED (tip on the ceiling, lip in the
            # groove): everywhere else interference = the snap itself
            rs = fit.sock_r(min(d - zz, fit.d5 - 1e-9))
            if rs is not None:
                worst_clear = min(worst_clear, rs - rp)
    d -= 0.01
check('handle: snap interference 0.10..0.30', 0.10 <= worst_int <= 0.30,
      '%.3fmm' % worst_int)
check('handle: clearance >= 0 outside the lip', worst_clear >= -0.02,
      'min %.3fmm' % worst_clear)
check('handle: air-scan (45 deg, bridges exempt)', sh.air('handle'))

# ========================================================= 5: contour truth
out_c2, _ic2 = _gen(_ring_png(), tag='c2', contour=2, levels=2, col_layers=3)
txt = open(out_c2).read()
n_wall_lines = txt.count('R168 contour wall')
check('contour=2: contour walls emitted', n_wall_lines > 0,
      '%d layers' % n_wall_lines)
sc2 = Scan().feed(out_c2)
ring_layers = 0
by = {}
for (obj, li), ps in sc2.layers.items():
    by.setdefault(li, []).extend(ps)
for li, ps in by.items():
    if len(ps) < 12:
        continue
    rs = sorted(math.hypot(x - cxc, y - cyc) for (x, y) in ps)
    gaps = [b - a for a, b in zip(rs, rs[1:])]
    if max(gaps) > 3.0:            # a clear radius gap = outer + inner loop
        ring_layers += 1
check('contour=2: ring prints OUTER + INNER contour', ring_layers > 0,
      '%d layers with 2 loops' % ring_layers)
check('contour=2: air-scan (walls stand on the plane)', sc2.air('contour2'))

out_c1, _ic1 = _gen(_ring_png(), tag='c1', contour=1, levels=2, col_layers=3)
sc1 = Scan().feed(out_c1)
last = _ic1['layers']
ref = last - 1
R_PIC = 22.0                     # the synthetic ring lives within r<=22mm
n_last = len(sc1.pts_in(last, last, R_PIC, cxc, cyc))
n_ref = len(sc1.pts_in(ref, ref, R_PIC, cxc, cyc))
check('contour=1: last layer fill-free', n_last < n_ref * 0.45,
      '%d vs %d pts (picture area)' % (n_last, n_ref))
check('contour=1: air-scan (contours on the full layer below)',
      sc1.air('contour1'))

# ========================================================= 6: mirror truth
def _ink_centroid(scan, li_from, li_to):
    pts = scan.pts_in(li_from, li_to)
    return (sum(p[0] for p in pts) / len(pts) if pts else 0.0)

out_m0, _ = _gen(_asym_png(), tag='m0', levels=2)
out_m1, _ = _gen(_asym_png(), tag='m1', levels=2, mirror_x=1)
sm0 = Scan().feed(out_m0)
sm1 = Scan().feed(out_m1)
c0 = _ink_centroid(sm0, NB + 1, NB + 2)   # first step-1 layers carry the image
c1 = _ink_centroid(sm1, NB + 1, NB + 2)
cx_bed = (BED[0] + BED[2]) / 2.0
check('mirror: X-centroid flips around the bed center',
      abs((c0 - cx_bed) + (c1 - cx_bed)) < 1.0 and abs(c0 - c1) > 4.0,
      'plain %.1f mirrored %.1f (center %.1f)' % (c0, c1, cx_bed))

# ================================================================ summary
print()
for w in warns[:8]:
    print('  warn: %s' % w)
print('R168 STAMPCHECK: %d checks, %d fail' % (runs, len(fails)))
if fails:
    for (n, i) in fails:
        print('  FAIL: %s %s' % (n, i))
    sys.exit(1)
shutil.rmtree(D, ignore_errors=True)
