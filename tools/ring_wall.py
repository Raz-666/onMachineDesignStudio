"""Stitch consecutive per-revolution rings into an open wall-surface mesh.

Contract: rings come from spiral_rings over ONE monotonic path, with equal
sample counts. Sample index j of consecutive rings is one pitch apart in
height, so index correspondence assumes the caller's pitch equals one full
XY revolution. The result is an OPEN centreline surface: no caps, no bead
width, no solid interior, never export-ready. Self-intersection between wall
quads is NOT validated here.
"""
import math
from pathlib import Path
import tempfile

from contour_mesh import _boundary, binary_stl, MAX_TRIANGLES
from stl_audit import inspect_stl


def _normalized_ring(points, samples):
    if len(points) != samples:
        raise ValueError('ring sample count mismatch')
    ring=[tuple(p) for p in points]
    if any(len(p)!=3 or any(not math.isfinite(v) for v in p) for p in ring):
        raise ValueError('finite XYZ ring points required')
    if any(a==b for a,b in zip(ring,ring[1:])) or ring[0]==ring[-1]:
        raise ValueError('duplicate consecutive ring points')
    xy=[(p[0],p[1]) for p in ring]
    _boundary(xy)  # simple polygon; collinear or crossing rings refused
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(xy,xy[1:]+xy[:1]))
    return ring[::-1] if area < 0 else ring


def stitch_wall_triangles(rings):
    """Validate rings and build wall triangles; returns (triangles, samples, bands)."""
    rings=list(rings)
    if len(rings) < 2:
        raise ValueError('at least two rings required')
    samples={ring.get('samples') for ring in rings}
    if len(samples) != 1:
        raise ValueError('all rings must share one sample count')
    n=samples.pop()
    if not 3 <= n <= 256:
        raise ValueError('ring sample count must stay in 3..256')
    if 2*(len(rings)-1)*n > MAX_TRIANGLES:
        raise ValueError('combined triangle budget exceeded')
    prepared=[_normalized_ring(ring['points_mm'],n) for ring in rings]
    bands=[ring['z_band_mm'] for ring in rings]
    for lower,upper in zip(bands,bands[1:]):
        if not lower[1] < upper[0]:
            raise ValueError('ring height bands must be disjoint and ascending')
    triangles=[]
    for lower,upper in zip(prepared,prepared[1:]):
        for j in range(n):
            a0,a1=lower[j],lower[(j+1)%n]
            b0,b1=upper[j],upper[(j+1)%n]
            triangles.append((a0,a1,b1))
            triangles.append((a0,b1,b0))
    for a,b,c in triangles:
        u=(b[0]-a[0],b[1]-a[1],b[2]-a[2])
        v=(c[0]-a[0],c[1]-a[1],c[2]-a[2])
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        if not any(abs(component) > 0 for component in cross):
            raise ValueError('degenerate wall triangle')
    return triangles,n,bands


def ring_wall_mesh(rings):
    """Return (binary_stl_bytes, report) for the stitched open wall surface."""
    triangles,n,bands=stitch_wall_triangles(rings)
    data=binary_stl(triangles)
    with tempfile.TemporaryDirectory(prefix='r2-ring-wall-') as directory:
        path=Path(directory)/'wall.stl'
        path.write_bytes(data)
        audit=inspect_stl(path)
    expected_boundary=2*n
    for key in ('nonmanifold_edges','duplicate_faces','normal_errors','degenerate_faces'):
        if audit[key]:
            raise ValueError('wall failed mesh check: '+key)
    # The audit counts every boundary edge as a direction imbalance, so for a
    # consistently oriented open wall the imbalance must equal the open boundary.
    if audit['boundary_edges'] != expected_boundary or audit['winding_errors'] != expected_boundary:
        raise ValueError('wall must stay open only at the first and last ring')
    if audit['vertex_connected_components'] != 1:
        raise ValueError('wall must be one connected surface')
    return data,dict(schema='r2-ring-wall/1',experimental=True,export_ready=False,
                     ring_count=len(rings),samples_per_ring=n,
                     triangles=len(triangles),
                     open_boundary_edges=audit['boundary_edges'],
                     expected_boundary_edges=expected_boundary,
                     height_bands_mm=bands,audit=audit,
                     limitations=['open surface: no caps, no solid interior, no bead width',
                                 'index correspondence assumes pitch equals one full XY revolution',
                                 'self-intersection between wall quads is not validated',
                                 'centreline geometry, not recovered CAD'])
