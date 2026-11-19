"""Experimental physical-boundary estimates with explicit width assumptions.

Not connected to automatic G-code/STL export. Caller must classify outer/hole
rings and establish layer height/filament units/flow. No guessed nozzle width.
Constant-width, topology-preserving miter rings only. Topology-changing and
variable-width offsets require a boolean backend, not silent repairs here.
"""
import math
from contour_mesh import _boundary, _cross, EPS


def width_from_filament(*, filament_mm, path_length_mm, layer_height_mm, filament_diameter_mm):
    """Stadium-section estimate, not a measurement of deposited material.

    A = E*pi*d²/(4*L); A = h*(w-h) + pi*h²/4. No M221/PA/volumetric
    corrections are assumed. Inputs must already be effective filament-mm.
    """
    values=(filament_mm,path_length_mm,layer_height_mm,filament_diameter_mm)
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('positive finite physical inputs required')
    area=filament_mm*math.pi*filament_diameter_mm**2/(4*path_length_mm)
    h=layer_height_mm
    width=area/h+h*(1-math.pi/4)
    if not math.isfinite(width) or width < h:
        raise ValueError('extrusion cannot support the assumed stadium cross-section')
    return dict(width_mm=width, cross_section_mm2=area,
                model='stadium', measured=False,
                assumptions='effective filament-mm, constant layer height, no unmodelled flow compensation')


def _offset_centerline(points, *, width_mm, role, max_miter_ratio=4.0, convex_only=True):
    """Offset a classified centreline by half its constant width.

    Outer perimeter: outward from its enclosed area. Hole perimeter: inward
    into its enclosed void. Does not resolve nesting/intersections between rings.
    Miter corners are an explicit approximation, not rounded bead geometry.
    Returned winding is normalized CCW; input vertices are never modified.
    """
    if role not in ('outer','hole'):
        raise ValueError('explicit outer or hole classification required')
    if not math.isfinite(width_mm) or width_mm <= 0:
        raise ValueError('positive finite width required')
    if not math.isfinite(max_miter_ratio) or max_miter_ratio < 1:
        raise ValueError('finite miter ratio >= 1 required')
    ring=_boundary(points)
    n=len(ring)
    if convex_only and any(_cross(ring[i-1],ring[i],ring[(i+1)%n]) <= EPS for i in range(n)):
        raise ValueError('only strictly convex centreline rings supported')
    distance=width_mm/2*(1 if role=='outer' else -1)
    directions=[]
    normals=[]
    for a,b in zip(ring,ring[1:]+ring[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy)
        directions.append((dx/length,dy/length))
        normals.append((dy/length,-dx/length))  # outward for CCW
    shifted=[]
    for i,p in enumerate(ring):
        prev,cur=normals[i-1],normals[i]
        denominator=1+prev[0]*cur[0]+prev[1]*cur[1]
        if denominator <= EPS:
            raise ValueError('unstable offset corner')
        delta=(distance*(prev[0]+cur[0])/denominator,
               distance*(prev[1]+cur[1])/denominator)
        if math.hypot(*delta) > abs(distance)*max_miter_ratio:
            raise ValueError('corner exceeds explicit miter limit')
        shifted.append((p[0]+delta[0],p[1]+delta[1]))
    # Inward offsets can disappear or reverse edge direction before the new
    # polygon looks self-intersecting. Reject instead of resurrecting a void.
    for i,(a,b) in enumerate(zip(shifted,shifted[1:]+shifted[:1])):
        dx,dy=directions[i]
        if (b[0]-a[0])*dx+(b[1]-a[1])*dy <= EPS:
            raise ValueError('offset collapses or reverses an edge')
    _boundary(shifted)
    # Keep the same oriented corners: do not accept an offset after a local
    # topology event, even if the resulting polygon happens to look simple.
    for i in range(n):
        before=_cross(ring[i-1],ring[i],ring[(i+1)%n])
        after=_cross(shifted[i-1],shifted[i],shifted[(i+1)%n])
        if before*after <= 0:
            raise ValueError('offset changes corner orientation')
    return dict(points_mm=shifted, width_mm=width_mm, role=role,
                signed_offset_mm=distance, join='miter',max_miter_ratio=max_miter_ratio,
                max_vertex_displacement_mm=max(math.dist(a,b) for a,b in zip(ring,shifted)),
                model='constant-width topology-preserving miter offset',export_ready=False)


def offset_convex_centerline(points, *, width_mm, role, max_miter_ratio=4.0):
    """Compatibility API: explicitly reject concave input rings."""
    return _offset_centerline(points,width_mm=width_mm,role=role,
                              max_miter_ratio=max_miter_ratio,convex_only=True)


def offset_simple_centerline(points, *, width_mm, role, max_miter_ratio=4.0):
    """Convex/concave simple rings, only while offset topology is preserved.

    No clipping, splitting, merging or hole deletion. Self-intersections,
    reversed edges and collapsed corners cause explicit failure. Caller must
    still validate relationships between offset rings (e.g. via prism_mesh).
    """
    return _offset_centerline(points,width_mm=width_mm,role=role,
                              max_miter_ratio=max_miter_ratio,convex_only=False)


def vertex_normal_offset(points, *, width_mm, role):
    """Offset each vertex along its averaged edge normal by half the width.

    Keeps a strict 1:1 vertex correspondence (no miter spikes, no bevel
    insertions), so per-vertex heights survive. Exact on circles; corners
    follow the averaged vertex normal, so corner-adjacent edges shift less
    than w/2 and the offset point deviates from the exact miter corner by at
    most the offset distance.
    Topology must be preserved: simple polygon, unchanged corner orientation
    and edge directions, or rejection.
    """
    if role not in ('outer','hole'):
        raise ValueError('explicit outer or hole classification required')
    if not math.isfinite(width_mm) or width_mm <= 0:
        raise ValueError('positive finite width required')
    ring=_boundary(points)
    n=len(ring)
    distance=width_mm/2*(1 if role=='outer' else -1)
    normals=[]
    for a,b in zip(ring,ring[1:]+ring[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy)
        normals.append((dy/length,-dx/length))
    shifted=[]
    for i,p in enumerate(ring):
        nx=normals[i-1][0]+normals[i][0]
        ny=normals[i-1][1]+normals[i][1]
        length=math.hypot(nx,ny)
        if length <= 1e-12:
            raise ValueError('unstable offset corner')
        shifted.append((p[0]+distance*nx/length,p[1]+distance*ny/length))
    _boundary(shifted)
    for i in range(n):
        if _cross(ring[i-1],ring[i],ring[(i+1)%n])*_cross(shifted[i-1],shifted[i],shifted[(i+1)%n]) <= 0:
            raise ValueError('offset changes corner orientation')
        dx,dy=ring[(i+1)%n][0]-ring[i][0],ring[(i+1)%n][1]-ring[i][1]
        ex,ey=shifted[(i+1)%n][0]-shifted[i][0],shifted[(i+1)%n][1]-shifted[i][1]
        if dx*ex+dy*ey <= 0:
            raise ValueError('offset collapses or reverses an edge')
    return dict(points_mm=shifted,width_mm=width_mm,role=role,
                signed_offset_mm=distance,join='vertex_normal',
                max_vertex_displacement_mm=abs(distance),
                deviation_note='exact on circles; corner-adjacent edges shift less than w/2 and corners deviate from the exact miter offset by at most the offset distance',
                model='constant-width vertex-normal offset',export_ready=False)
