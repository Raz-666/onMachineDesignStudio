"""Explicit per-revolution ring sampling of monotonic nonplanar paths.

Contract for vase-style spiral walls: the caller supplies the XYZ points of ONE
connected extrusion path whose height changes strictly monotonically, plus an
explicit pitch (height of exactly one full XY revolution) and a sample count
per revolution. Ring r collects the chord-interpolated samples whose heights
cover [z_start + r*pitch, z_start + (r+1)*pitch). Ring points therefore mix
heights within one pitch band, and the pitch/revolution correspondence itself
is a caller assumption, not something verified here. Rings stay nozzle
centreline without bead width and are never export-ready.
"""
import math
from contour_mesh import _boundary

MAX_POINTS = 1024
MAX_SAMPLES = 256


def spiral_rings(points, *, pitch_mm, samples_per_revolution):
    """Return validated nonplanar centreline rings, one per full revolution."""
    if not math.isfinite(pitch_mm) or pitch_mm <= 0:
        raise ValueError('positive finite pitch required')
    if type(samples_per_revolution) is not int or not 3 <= samples_per_revolution <= MAX_SAMPLES:
        raise ValueError('sample count per revolution must be an int in 3..256')
    if not 3 <= len(points) <= MAX_POINTS:
        raise ValueError('path point budget exceeded or insufficient points')
    pts=[tuple(p) for p in points]
    if any(len(p)!=3 or any(not math.isfinite(v) for v in p) for p in pts):
        raise ValueError('finite XYZ points required')
    if any(a==b for a,b in zip(pts,pts[1:])):
        raise ValueError('duplicate consecutive points')
    zs=[p[2] for p in pts]
    ascending=all(b>a for a,b in zip(zs,zs[1:]))
    descending=all(b<a for a,b in zip(zs,zs[1:]))
    if not (ascending or descending):
        raise ValueError('path height must change strictly monotonically')
    span=abs(zs[-1]-zs[0])
    if span < pitch_mm:
        raise ValueError('pitch exceeds the path height span')
    step=pitch_mm/samples_per_revolution
    direction=1.0 if ascending else -1.0
    samples=[]
    index=0
    k=0
    while True:
        height=zs[0]+direction*k*step
        if ascending:
            if not zs[0] <= height < zs[-1]:
                break
            while index+1 < len(pts) and pts[index+1][2] <= height:
                index += 1
        else:
            if not zs[-1] < height <= zs[0]:
                break
            while index+1 < len(pts) and pts[index+1][2] >= height:
                index += 1
        if index+1 >= len(pts):
            break
        a,b=pts[index],pts[index+1]
        t=(height-a[2])/(b[2]-a[2])
        samples.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]),height))
        k += 1
    rings=[]
    dropped=0
    for r in range(len(samples)//samples_per_revolution):
        ring=samples[r*samples_per_revolution:(r+1)*samples_per_revolution]
        _boundary([(x,y) for x,y,z in ring])  # simple XY polygon; crossing rings refused
        z_values=[z for x,y,z in ring]
        rings.append(dict(samples=len(ring),
                          z_band_mm=[min(z_values),max(z_values)],
                          points_mm=ring))
    dropped=len(samples)-len(rings)*samples_per_revolution
    if not rings:
        raise ValueError('no complete revolution ring in path')
    return dict(rings=rings,ring_count=len(rings),
                dropped_incomplete_ring_samples=dropped,
                geometry='nozzle_centerline_per_revolution_rings',
                direction='ascending' if ascending else 'descending',
                height_span_mm=dict(min=min(zs),max=max(zs)),
                export_ready=False,
                limitations=['linear chord interpolation between recorded vertices, not the true curve',
                             'ring points mix heights within one pitch band',
                             'pitch equal to one full XY revolution is a caller assumption, not verified',
                             'centreline rings; bead width not applied',
                             'no reordering or smoothing'])
