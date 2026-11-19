"""Close a sampled vase wall with vertical-projection caps.

Contract: the first and last wall rings are closed along their boundary by
vertical strips (each boundary vertex moves ONLY along z) down/up to the
caller-supplied cap planes, and the caps are ear-clipped from the flattened
ring XY. Vertical deviation is therefore bounded by the ring's own height
band (at most one pitch) and is reported per cap. The result is a closed
surface; its volume assumes a non-self-overlapping shell, which is NOT
validated here unless check_self_intersection=True audits the shipped
float32 triangles (non-adjacent pairs; touching counts; folds through a
shared vertex are not classified). Centreline geometry, no bead width,
never export-ready.
"""
import math
from pathlib import Path
import tempfile

from contour_mesh import _caps, binary_stl, MAX_TRIANGLES
from ring_wall import stitch_wall_triangles
from self_intersect import self_intersections, triangles_from_stl
from stl_audit import inspect_stl


def _strip(lower, upper, n):
    """Vertical quads between two rings that share XY per index.

    A quad whose two rings share an exact vertex collapses to one triangle;
    the skipped duplicate is counted, never silently repaired.
    """
    triangles=[]
    collapsed=0
    for j in range(n):
        a0,a1=lower[j],lower[(j+1)%n]
        b0,b1=upper[j],upper[(j+1)%n]
        for triangle in ((a0,a1,b1),(a0,b1,b0)):
            if len(set(triangle)) < 3:
                collapsed+=1
                continue
            triangles.append(triangle)
    return triangles,collapsed


def _cap(ring, z, *, outward_up):
    xy=[(p[0],p[1]) for p in ring]
    triangles=[(xy[a],xy[b],xy[c]) for a,b,c in _caps(xy)]
    cap=[((a[0],a[1],z),(b[0],b[1],z),(c[0],c[1],z)) for a,b,c in triangles]
    return cap if outward_up else [(t[0],t[2],t[1]) for t in cap]


def _check_not_degenerate(triangles):
    for a,b,c in triangles:
        u=(b[0]-a[0],b[1]-a[1],b[2]-a[2])
        v=(c[0]-a[0],c[1]-a[1],c[2]-a[2])
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        if not any(abs(component) > 0 for component in cross):
            raise ValueError('degenerate closure triangle')


def close_vase_surface(rings, *, bottom_z, top_z, check_self_intersection=False):
    """Return (binary_stl_bytes, report) for the closed vase centreline surface."""
    rings=list(rings)
    wall,n,bands=stitch_wall_triangles(rings)
    if not (math.isfinite(bottom_z) and math.isfinite(top_z) and top_z > bottom_z):
        raise ValueError('positive finite cap planes required')
    first=[(p[0],p[1],p[2]) for p in rings[0]['points_mm']]
    last=[(p[0],p[1],p[2]) for p in rings[-1]['points_mm']]
    bottom_deviation=[p[2]-bottom_z for p in first]
    top_deviation=[top_z-p[2] for p in last]
    if any(d < 0 for d in bottom_deviation) or any(d < 0 for d in top_deviation):
        raise ValueError('cap planes must not cut into the wall rings')
    bottom_cap_ring=[(p[0],p[1],bottom_z) for p in first]
    top_cap_ring=[(p[0],p[1],top_z) for p in last]
    bottom_strip,bottom_collapsed=_strip(bottom_cap_ring,first,n)
    top_strip,top_collapsed=_strip(last,top_cap_ring,n)
    triangles=(wall
               +bottom_strip
               +_cap(first,bottom_z,outward_up=False)
               +top_strip
               +_cap(last,top_z,outward_up=True))
    if len(triangles) > MAX_TRIANGLES:
        raise ValueError('combined triangle budget exceeded')
    _check_not_degenerate(triangles)
    data=binary_stl(triangles)
    with tempfile.TemporaryDirectory(prefix='r2-vase-closure-') as directory:
        path=Path(directory)/'vase.stl'
        path.write_bytes(data)
        audit=inspect_stl(path)
    for key in ('nonmanifold_edges','duplicate_faces','normal_errors',
                'winding_errors','degenerate_faces'):
        if audit[key]:
            raise ValueError('closure failed mesh check: '+key)
    if audit['boundary_edges'] or audit['vertex_connected_components']!=1:
        raise ValueError('closure must be one fully closed component')
    if audit['signed_volume'] <= 0:
        raise ValueError('closure must enclose a positive volume')
    self_check=None
    if check_self_intersection:
        with tempfile.TemporaryDirectory(prefix='r2-vase-selfcheck-') as directory:
            path=Path(directory)/'vase.stl'
            path.write_bytes(data)
            self_check=self_intersections(triangles_from_stl(path))
        if self_check['intersecting_pair_count']:
            raise ValueError('closure failed mesh check: self-intersection (%d pairs)'
                             % self_check['intersecting_pair_count'])
    limitations=['volume assumes a non-self-overlapping shell; self-intersection is not validated',
                                 'centreline surface; bead width not applied',
                                 'cap planes are caller-supplied, not recovered from G-code',
                                 'pitch equals one full XY revolution is a caller assumption']
    if self_check is not None:
        limitations=limitations[1:]
    return data,dict(schema='r2-vase-surface/1',experimental=True,export_ready=False,
                     ring_count=len(rings),samples_per_ring=n,
                     triangles=len(triangles),
                     caps=dict(bottom_z_mm=bottom_z,top_z_mm=top_z,
                               bottom_max_vertical_deviation_mm=max(bottom_deviation),
                               top_max_vertical_deviation_mm=max(top_deviation),
                               bottom_collapsed_strip_triangles=bottom_collapsed,
                               top_collapsed_strip_triangles=top_collapsed,
                               contract='boundary vertices move only along z; deviation bounded by one pitch band'),
                     audit=audit,
                     self_intersection=self_check,
                     limitations=limitations)


def rim_agreement(ring, rim_points):
    """Measure how far a flattened ring sits from a recorded planar rim loop.

    ring may be a ring dict from sample_wall_run or a list of 3D points.
    """
    if isinstance(ring,dict):
        ring=ring['points_mm']
    ring_xy=[(p[0],p[1]) for p in ring]
    rim=[(p[0],p[1]) for p in rim_points]
    if len(rim) < 3 or any(a==b for a,b in zip(rim,rim[1:])):
        raise ValueError('distinct rim points required')
    if rim[0]==rim[-1]:
        rim=rim[:-1]
    if len(rim) < 3:
        raise ValueError('rim needs at least three distinct points')
    segments=list(zip(rim,rim[1:]+rim[:1]))
    def distance(point):
        best=float('inf')
        for a,b in segments:
            dx,dy=b[0]-a[0],b[1]-a[1]
            t=0.0 if dx==dy==0 else max(0.0,min(1.0,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy)))
            best=min(best,math.hypot(point[0]-(a[0]+t*dx),point[1]-(a[1]+t*dy)))
        return best
    def area(points):
        return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2
    distances=[distance(p) for p in ring_xy]
    return dict(ring_vertices=len(ring_xy),rim_vertices=len(rim),
                ring_area_mm2=area(ring_xy),rim_area_mm2=area(rim),
                area_difference_mm2=abs(area(ring_xy)-area(rim)),
                max_distance_mm=max(distances),
                mean_distance_mm=sum(distances)/len(distances),
                measured='flattened ring vertices to rim polyline')
