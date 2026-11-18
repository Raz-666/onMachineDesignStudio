"""Experimental contour-to-surface foundation, NOT the active G-code exporter.

Input is an already classified physical boundary in mm, not a nozzle centreline.
This stage supports one simple vertical prism with disjoint through-holes. It intentionally
rejects ambiguous/degenerate boundaries instead of repairing them. No dependency
on Klipper or the watcher. Offsets, changing layer topology and G-code
classification must be implemented before production integration.
"""
import math
import struct

MAX_SECTIONS = 64
MAX_TRIANGLES = 32768
MAX_VERTICES = 256  # bound quadratic validation and cubic worst-case ear clipping
EPS = 1e-10  # conservative rejection threshold in oriented area (mm squared)


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _on_segment(a, b, p):
    return (abs(_cross(a, b, p)) <= EPS and
            min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _intersects(a, b, c, d):
    x, y, z, w = _cross(a,b,c), _cross(a,b,d), _cross(c,d,a), _cross(c,d,b)
    return ((x*y < 0 and z*w < 0) or _on_segment(a,b,c) or
            _on_segment(a,b,d) or _on_segment(c,d,a) or _on_segment(c,d,b))


def _boundary(points):
    if not 3 <= len(points) <= MAX_VERTICES + 1:
        raise ValueError('boundary must have 3..256 vertices')
    if any(len(p) != 2 for p in points):
        raise ValueError('boundary vertices must be XY pairs')
    points = [tuple(float(v) for v in p) for p in points]
    if not all(math.isfinite(v) and abs(v) <= 100000 for p in points for v in p):
        raise ValueError('coordinates must be finite and within +/-100000 mm')
    if points[0] == points[-1]:
        points.pop()  # explicit closure and implicit closure mean the same polygon
    n = len(points)
    if not 3 <= n <= MAX_VERTICES or len(set(points)) != n:
        raise ValueError('invalid vertex count or repeated vertex')
    for i in range(n):
        if abs(_cross(points[i-1], points[i], points[(i+1)%n])) <= EPS:
            raise ValueError('collinear or degenerate boundary corner')
        for j in range(i+1, n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            if _intersects(points[i], points[(i+1)%n], points[j], points[(j+1)%n]):
                raise ValueError('boundary self-intersects or touches itself')
    area2 = math.fsum(_cross(points[0], points[i], points[i+1]) for i in range(1,n-1))
    if abs(area2) <= EPS:
        raise ValueError('zero area boundary')
    return points if area2 > 0 else points[::-1]


def _caps(points):
    """Ear clipping for a validated simple CCW polygon, including concavity."""
    remaining = list(range(len(points)))
    triangles = []
    while len(remaining) > 3:
        for k, b in enumerate(remaining):
            a, c = remaining[k-1], remaining[(k+1)%len(remaining)]
            if _cross(points[a], points[b], points[c]) <= EPS:
                continue
            if any(all(_cross(points[u], points[v], points[p]) >= -EPS
                       for u,v in ((a,b),(b,c),(c,a)))
                   for p in remaining if points[p] not in (points[a],points[b],points[c])):
                continue
            triangles.append((a,b,c))
            del remaining[k]
            break
        else:
            raise ValueError('boundary cannot be triangulated without degeneracy')
    triangles.append(tuple(remaining))
    return triangles


def _inside(point, ring):
    """Strict containment; boundary contacts are not interior."""
    inside = False
    x,y = point
    for a,b in zip(ring, ring[1:]+ring[:1]):
        if _on_segment(a,b,point):
            return False
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                inside = not inside
    return inside


def _with_holes(outer, holes):
    """Build a weakly simple cap ring using visible, zero-area bridges.

    All rings must already be simple. Reject nested, intersecting or touching
    rings. Bridges only affect cap triangulation, never side-wall geometry.
    """
    rings = [outer] + holes
    for i, ring in enumerate(rings):
        for other in rings[i+1:]:
            if any(_intersects(a,b,c,d)
                   for a,b in zip(ring,ring[1:]+ring[:1])
                   for c,d in zip(other,other[1:]+other[:1])):
                raise ValueError('rings intersect or touch')
    for i, hole in enumerate(holes):
        if not _inside(hole[0], outer):
            raise ValueError('hole outside outer contour')
        if any(_inside(hole[0], other) or _inside(other[0], hole)
               for other in holes[i+1:]):
            raise ValueError('nested holes require explicit island hierarchy')
    merged = outer[:]
    bridges = []
    edges = [(a,b) for ring in rings for a,b in zip(ring,ring[1:]+ring[:1])]
    for hole in holes:
        candidates = []
        for i,a in enumerate(merged):
            for j,b in enumerate(hole):
                # Incident edges may meet at the bridge endpoint, not overlap it.
                blocked = False
                for c,d in edges + bridges:
                    if a in (c,d) or b in (c,d):
                        other = d if c in (a,b) else c
                        if _on_segment(a,b,other) or abs(_cross(a,b,other)) <= EPS:
                            blocked = True
                            break
                    elif _intersects(a,b,c,d):
                        blocked = True
                        break
                midpoint = ((a[0]+b[0])/2,(a[1]+b[1])/2)
                if not blocked and _inside(midpoint,outer) and not any(_inside(midpoint,h) for h in holes):
                    candidates.append(((a[0]-b[0])**2+(a[1]-b[1])**2,i,j))
        if not candidates:
            raise ValueError('no unambiguous visible bridge for hole')
        _,i,j = min(candidates)
        bridges.append((merged[i],hole[j]))
        merged = merged[:i+1] + hole[j:] + hole[:j+1] + [merged[i]] + merged[i+1:]
    return merged


def prism_mesh(boundary, z_bottom, z_top, *, holes=()):
    """Outward surface of a prism with explicitly classified through-holes.

    Holes are not inferred from toolpaths. No internal layer caps or bridge
    walls are produced. Nested holes/islands and changing layers are rejected
    or outside this API's scope. Input loops may use either orientation.
    """
    if len(boundary) + sum(len(h) for h in holes) + 2*len(holes) > MAX_VERTICES:
        raise ValueError('combined contour/bridge vertex budget exceeded')
    outer = _boundary(boundary)
    inner = [_boundary(h)[::-1] for h in holes]  # clockwise: normals into void
    points = _with_holes(outer,inner) if inner else outer
    if not all(math.isfinite(z) and abs(z) <= 100000 for z in (z_bottom,z_top)) or z_top <= z_bottom:
        raise ValueError('finite increasing Z bounds required')
    bottom = [(x,y,float(z_bottom)) for x,y in points]
    top = [(x,y,float(z_top)) for x,y in points]
    triangles = []
    caps = _caps(points)
    expected_area2 = math.fsum(_cross(r[0],r[i],r[i+1])
                              for r in [outer]+inner for i in range(1,len(r)-1))
    cap_area2 = math.fsum(_cross(points[a],points[b],points[c]) for a,b,c in caps)
    if not math.isclose(cap_area2, expected_area2, rel_tol=1e-9, abs_tol=EPS):
        raise ValueError('cap area does not preserve outer contour minus holes')
    for a,b,c in caps:
        if _cross(points[a],points[b],points[c]) <= EPS:
            raise ValueError('degenerate cap triangulation')
        triangles.extend(((bottom[c],bottom[b],bottom[a]), (top[a],top[b],top[c])))
    for ring in [outer]+inner:
        for a,b in zip(ring,ring[1:]+ring[:1]):
            lo_a,lo_b = (*a,float(z_bottom)),(*b,float(z_bottom))
            hi_a,hi_b = (*a,float(z_top)),(*b,float(z_top))
            triangles.extend(((lo_a,lo_b,hi_b),(lo_a,hi_b,hi_a)))
    return triangles


def loft_mesh(boundary, sections, *, holes=()):
    """Surface through translated/uniformly scaled copies of one boundary.

    Each section is (z_mm, positive_scale, x_offset_mm, y_offset_mm).
    Scaling is around XY=(0,0), then offset is added. All holes undergo the
    SAME transform. Between sections, coordinates interpolate linearly.
    This deliberately does not guess correspondence between arbitrary loops.
    Positive uniform scale preserves the polygon hierarchy throughout each
    interval; rotation, independent hole motion, splits/merges are unsupported.
    """
    if not 2 <= len(sections) <= MAX_SECTIONS:
        raise ValueError('loft requires 2..64 sections')
    normalized = []
    for section in sections:
        if len(section) != 4:
            raise ValueError('section must be (z, scale, dx, dy)')
        z,scale,dx,dy = map(float, section)
        if not all(math.isfinite(v) for v in (z,scale,dx,dy)) or scale <= 0:
            raise ValueError('finite section values and positive scale required')
        if abs(z) > 100000 or (normalized and z <= normalized[-1][0]):
            raise ValueError('Z sections must increase and stay within bounds')
        normalized.append((z,scale,dx,dy))
    # Reuse ring validation and cap triangulation without introducing layer caps.
    prototype = prism_mesh(boundary,0,1,holes=holes)
    rings = [_boundary(boundary)] + [_boundary(h)[::-1] for h in holes]

    def transform(point, section):
        z,scale,dx,dy = section
        x,y = point[0]*scale+dx, point[1]*scale+dy
        if not all(math.isfinite(v) and abs(v) <= 100000 for v in (x,y)):
            raise ValueError('transformed contour outside coordinate bounds')
        return x,y,z

    # Cache transformed rings; shared vertices are byte-identical at layer seams.
    layers = [[[transform(p,section) for p in ring] for ring in rings]
              for section in normalized]
    triangles = []
    for triangle in prototype:
        heights = {p[2] for p in triangle}
        if heights == {0.0}:
            triangles.append(tuple(transform(p,normalized[0]) for p in triangle))
        elif heights == {1.0}:
            triangles.append(tuple(transform(p,normalized[-1]) for p in triangle))
    for lower,upper in zip(layers,layers[1:]):
        for lo,hi in zip(lower,upper):
            for i in range(len(lo)):
                j = (i+1)%len(lo)
                triangles.extend(((lo[i],lo[j],hi[j]),(lo[i],hi[j],hi[i])))
    if len(triangles) > MAX_TRIANGLES:
        raise ValueError('experimental triangle budget exceeded')
    return triangles


def binary_stl(triangles):
    """Serialize small experimental meshes; validate after float32 conversion.

    Return bytes only; callers own file creation. This never overwrites a file.
    """
    if not 1 <= len(triangles) <= MAX_TRIANGLES:
        raise ValueError('experimental triangle budget exceeded or mesh empty')
    records = []
    for triangle in triangles:
        vertices = [struct.unpack('<3f', struct.pack('<3f', *v)) for v in triangle]
        a,b,c = vertices
        if not all(math.isfinite(v) for p in vertices for v in p):
            raise ValueError('non-finite vertex')
        u = [b[i]-a[i] for i in range(3)]
        v = [c[i]-a[i] for i in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(x*x for x in normal))
        if length <= EPS:
            raise ValueError('triangle collapsed at STL float32 precision')
        records.append(struct.pack('<12fH', *(x/length for x in normal), *a,*b,*c,0))
    return struct.pack('<80sI', b'R2 experimental contour surface; mm; not a G-code exporter', len(records)) + b''.join(records)
