#!/usr/bin/env python3
"""R287: numeric banding analysis - radial displacement per Z band."""
import re
import math

src = '/tmp/vtest/V02_ShapeCyl8seg70x70x150_vase_S100-100T65-65_2_TWR-30_TX.gcode'
moves = []
x = y = z = 0.0
e = 0.0
emode = True
cur_z = 0.0
xre = re.compile(r'X([-\d.]+)')
yre = re.compile(r'Y([-\d.]+)')
zre = re.compile(r'Z([-\d.]+)')
ere = re.compile(r'E([-\d.]+)')
for ln in open(src, errors='replace'):
    s = ln.strip()
    if s.startswith(';'):
        m = re.search(r'Z:([-\d.]+)', s)
        if m:
            cur_z = float(m.group(1))
        continue
    if s.startswith('M82'):
        emode = True
        continue
    if s.startswith('M83'):
        emode = False
        continue
    if s.startswith('G0') or s.startswith('G1'):
        nx, ny, nz, ne = x, y, z, e
        m = xre.search(s)
        if m:
            nx = float(m.group(1))
        m = yre.search(s)
        if m:
            ny = float(m.group(1))
        m = zre.search(s)
        if m:
            nz = float(m.group(1))
            cur_z = nz
        m = ere.search(s)
        if m:
            ne = float(m.group(1))
        ext = s.startswith('G1') and m is not None and ne != e
        if emode and ext:
            moves.append((cur_z, (x + nx) / 2, (y + ny) / 2))
        elif (not emode) and ext and ne > e:
            moves.append((cur_z, (x + nx) / 2, (y + ny) / 2))
        x, y, z, e = nx, ny, nz, ne

zs = [m[0] for m in moves]
zmin, zmax = min(zs), max(zs)
N = 100
band = (zmax - zmin) / N
prof = []
for i in range(N):
    za = zmin + i * band
    zb = za + band
    rad = [math.hypot(m[1], m[2]) for m in moves if za <= m[0] < zb]
    if rad:
        prof.append((za, sum(rad) / len(rad)))

print("Z-band -> radial displacement (mm)  (look for periodic ripple):")
for i, (za, r) in enumerate(prof):
    print("%3d z=%7.2f rad=%7.3f" % (i, za, r))

# periodicity check via autocorrelation of the radial profile
vals = [r for _, r in prof]
m = sum(vals) / len(vals)
var = sum((v - m) ** 2 for v in vals) / len(vals)
print("\nmean=%.4f stddev=%.5f" % (m, math.sqrt(var)))
print("variation amplitude: %.4f mm (%.2f%%)" % (math.sqrt(var), math.sqrt(var) / m * 100))
