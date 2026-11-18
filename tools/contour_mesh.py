"""Experimental contour-to-surface foundation, NOT the active G-code exporter.

Input is an already classified physical boundary in mm, not a nozzle centreline.
This first stage supports one simple, hole-free vertical prism. It intentionally
rejects ambiguous/degenerate boundaries instead of repairing them. No dependency
on Klipper or the watcher. Holes, offsets, changing layer topology and G-code
classification must be implemented before production integration.
"""
import math
import struct

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
                   for p in remaining if p not in (a,b,c)):
                continue
            triangles.append((a,b,c))
            del remaining[k]
            break
        else:
            raise ValueError('boundary cannot be triangulated without degeneracy')
    triangles.append(tuple(remaining))
    return triangles


def prism_mesh(boundary, z_bottom, z_top):
    """Return outward-oriented triangles of a single closed vertical prism.

    No internal layer caps are produced. Callers must not use this function to
    fill a contour containing holes; holes require a separate polygon hierarchy.
    """
    points = _boundary(boundary)
    if not all(math.isfinite(z) and abs(z) <= 100000 for z in (z_bottom,z_top)) or z_top <= z_bottom:
        raise ValueError('finite increasing Z bounds required')
    bottom = [(x,y,float(z_bottom)) for x,y in points]
    top = [(x,y,float(z_top)) for x,y in points]
    triangles = []
    for a,b,c in _caps(points):
        triangles.extend(((bottom[c],bottom[b],bottom[a]), (top[a],top[b],top[c])))
    for a in range(len(points)):
        b = (a+1)%len(points)
        triangles.extend(((bottom[a],bottom[b],top[b]), (bottom[a],top[b],top[a])))
    return triangles


def binary_stl(triangles):
    """Serialize small experimental meshes; validate after float32 conversion.

    Return bytes only; callers own file creation. This never overwrites a file.
    """
    if not 1 <= len(triangles) <= 4*MAX_VERTICES:
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
