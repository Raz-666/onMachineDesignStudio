"""Apply an explicit constant bead width to sampled spiral wall rings.

Each ring is offset in XY by half the width along vertex normals; every ring
point keeps its own recorded height (first-order vertical bead sides; the
spiral tilt of the bead is not corrected). Strict topology preservation per
ring or explicit rejection; a wall surface is only built when EVERY ring of
the span accepts the width. Never export-ready.
"""
from ring_wall import ring_wall_mesh
from physical_contours import vertex_normal_offset


def offset_wall_rings(rings, *, width_mm, side):
    """Offset all rings; returns (offset_rings, per-ring rejections)."""
    if side not in ('outer','inner'):
        raise ValueError("side must be 'outer' or 'inner'")
    role='outer' if side=='outer' else 'hole'
    offset_rings=[]
    rejections=[]
    for ring in rings:
        points=ring['points_mm']
        try:
            result=vertex_normal_offset([(p[0],p[1]) for p in points],
                                        width_mm=width_mm,role=role)
        except ValueError as exc:
            rejections.append(dict(z_band_mm=ring['z_band_mm'],samples=ring['samples'],
                                   reason=str(exc)))
            continue
        offset_rings.append(dict(samples=ring['samples'],
                                 z_band_mm=ring['z_band_mm'],
                                 points_mm=[(x,y,p[2]) for (x,y),p in zip(result['points_mm'],points)]))
    return offset_rings,rejections


def wall_surface(rings, *, width_mm, side):
    """Build the offset wall surface; rejects if any ring rejects the width."""
    offset_rings,rejections=offset_wall_rings(rings,width_mm=width_mm,side=side)
    if rejections or len(offset_rings)!=len(rings):
        raise ValueError('%s surface at width %.6g rejected for %d of %d rings; first reason: %s'
                         %(side,width_mm,len(rejections),len(rings),
                           rejections[0]['reason'] if rejections else 'missing rings'))
    data,report=ring_wall_mesh(offset_rings)
    report['side']=side
    report['width_mm']=width_mm
    report['join']='vertex_normal'
    report['assumption']='constant width; vertical bead sides; width itself is caller-supplied and unverified'
    return data,report
