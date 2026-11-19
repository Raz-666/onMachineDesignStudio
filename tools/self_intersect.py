"""Self-intersection audit for triangle surfaces; never repairs geometry.

Scope: any pair of NON-adjacent triangles (no shared vertex, welded by exact
coordinate equality exactly like stl_audit) must not intersect, even by
touching. Contacts between vertex-adjacent triangles (shared edge/vertex,
including folds through a shared vertex) are NOT classified. Coplanar overlap
is detected via dominant-axis projection. Broad phase is a spatial hash with
adaptive cell size (median triangle bounding-box diagonal); a pair may be
inserted into several cells and is tested once. R2 convention: millimetres,
pure stdlib, no runtime dependencies.
"""
import math
import struct
from pathlib import Path


def triangles_from_stl(path):
    """Read a binary STL into a list of float32 vertex tuples (as shipped)."""
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise ValueError('truncated binary STL header')
    count = struct.unpack_from('<I', data, 80)[0]
    if len(data) != 84+count*50:
        raise ValueError('triangle count does not match file length')
    triangles = []
    for i in range(count):
        values = struct.unpack_from('<12fH', data, 84+i*50)
        triangles.append((values[3:6], values[6:9], values[9:12]))
    return triangles


def _cross(u, v):
    return (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])


def _dot(u, v):
    return u[0]*v[0]+u[1]*v[1]+u[2]*v[2]


def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def _edges(triangle):
    a, b, c = triangle
    return ((a, b), (b, c), (c, a))


def _dominant_axis(normal):
    return max(range(3), key=lambda i: abs(normal[i]))


def _project(points, axis):
    return [(p[(axis+1) % 3], p[(axis+2) % 3]) for p in points]


def _orient2d(o, p, q):
    return (p[0]-o[0])*(q[1]-o[1])-(p[1]-o[1])*(q[0]-o[0])


def _on_segment2d(a, b, p, eps):
    if _orient2d(a, b, p) > eps or _orient2d(a, b, p) < -eps:
        return False
    return (min(a[0], b[0])-eps <= p[0] <= max(a[0], b[0])+eps
            and min(a[1], b[1])-eps <= p[1] <= max(a[1], b[1])+eps)


def _segments_touch2d(a0, a1, b0, b1, eps):
    d1 = _orient2d(b0, b1, a0)
    d2 = _orient2d(b0, b1, a1)
    d3 = _orient2d(a0, a1, b0)
    d4 = _orient2d(a0, a1, b1)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) \
            and ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    return any(_on_segment2d(s, t, p, eps)
               for p, s, t in ((a0, b0, b1), (a1, b0, b1),
                               (b0, a0, a1), (b1, a0, a1)))


def _point_in_triangle2d(point, triangle, eps):
    return all(_orient2d(a, b, point) >= -eps
               for a, b in _edges(triangle))


def _coplanar_overlap(a, b, axis, eps):
    """Both triangles lie in one plane; overlap test after dropping `axis`."""
    ta = _project(a, axis)
    tb = _project(b, axis)
    if any(_segments_touch2d(p, q, r, s, eps)
           for p, q in _edges(ta) for r, s in _edges(tb)):
        return True
    return (any(_point_in_triangle2d(p, tb, eps) for p in ta)
            or any(_point_in_triangle2d(p, ta, eps) for p in tb))


def _point_in_triangle(point, triangle, normal, eps):
    tolerance = eps*(math.sqrt(_dot(normal, normal))+1.0)
    a, b, c = triangle
    for start, end in _edges(triangle):
        if _dot(_cross(_sub(end, start), _sub(point, start)), normal) < -tolerance:
            return False
    return True


def _segment_hits_triangle(p, q, triangle, normal, eps):
    """True if segment pq intersects the triangle, touching included."""
    a, b, c = triangle
    dp = _dot(normal, _sub(p, a))
    dq = _dot(normal, _sub(q, a))
    if dp > eps and dq > eps:
        return False
    if dp < -eps and dq < -eps:
        return False
    if abs(dp) <= eps and _point_in_triangle(p, triangle, normal, eps):
        return True
    if abs(dq) <= eps and _point_in_triangle(q, triangle, normal, eps):
        return True
    if abs(dp) <= eps and abs(dq) <= eps:
        axis = _dominant_axis(normal)
        s0, s1 = _project((p, q), axis)
        return any(_segments_touch2d(s0, s1, r, u, eps)
                   for r, u in _edges(_project(triangle, axis)))
    if (dp > 0) != (dq > 0):
        t = dp/(dp-dq)
        x = (p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1]), p[2]+t*(q[2]-p[2]))
        return _point_in_triangle(x, triangle, normal, eps)
    return False


def triangles_intersect(a, b, eps=1e-9):
    """Conservative triangle-triangle test; touching counts as intersecting."""
    na = _cross(_sub(a[1], a[0]), _sub(a[2], a[0]))
    db = [_dot(na, _sub(p, a[0])) for p in b]
    if min(db) > eps or max(db) < -eps:
        return False
    nb = _cross(_sub(b[1], b[0]), _sub(b[2], b[0]))
    da = [_dot(nb, _sub(p, b[0])) for p in a]
    if min(da) > eps or max(da) < -eps:
        return False
    if max(abs(d) for d in db) <= eps and max(abs(d) for d in da) <= eps:
        return _coplanar_overlap(a, b, _dominant_axis(na), eps)
    if any(_segment_hits_triangle(p, q, b, nb, eps) for p, q in _edges(a)):
        return True
    return any(_segment_hits_triangle(p, q, a, na, eps) for p, q in _edges(b))


def _vertex_ids(triangles):
    ids = {}
    result = []
    for triangle in triangles:
        row = []
        for vertex in triangle:
            key = (float(vertex[0]), float(vertex[1]), float(vertex[2]))
            row.append(ids.setdefault(key, len(ids)))
        result.append(row)
    return result, len(ids)


def self_intersections(triangles, *, cell_size=None, eps=1e-9,
                       max_reported_pairs=100):
    """Audit a triangle surface for self-intersections.

    Raises ValueError on degenerate input triangles (audit only, never repair).
    Returns a report dict; `intersecting_pair_count` is the verdict, the
    pairs themselves are reported capped at `max_reported_pairs`.
    """
    triangles = list(triangles)
    if len(triangles) < 2:
        return dict(intersecting_pair_count=0, intersecting_pairs=[],
                    reported_pairs_capped=False, tested_pairs=0,
                    adjacent_pairs_skipped=0, candidate_pairs=0,
                    cell_size_mm=None, triangles=len(triangles),
                    limitations=['pairs sharing a vertex (folds through a '
                                 'shared vertex) are not classified'])
    ids, _ = _vertex_ids(triangles)
    boxes = []
    diagonals = []
    for triangle in triangles:
        low = [min(p[i] for p in triangle) for i in range(3)]
        high = [max(p[i] for p in triangle) for i in range(3)]
        boxes.append((*low, *high))
        diagonals.append(math.dist(low, high))
        u = _sub(triangle[1], triangle[0])
        v = _sub(triangle[2], triangle[0])
        if not any(component for component in _cross(u, v)):
            raise ValueError('degenerate triangle in input; audit refuses')
    if cell_size is None:
        ordered = sorted(diagonals)
        cell_size = max(ordered[len(ordered)//2], 1e-6)
    if not (math.isfinite(cell_size) and cell_size > 0):
        raise ValueError('positive finite cell size required')
    cells = {}
    eps_cell = eps
    for index, (low_x, low_y, low_z, high_x, high_y, high_z) in enumerate(boxes):
        span_x = int(math.floor((high_x+eps_cell)/cell_size))-int(math.floor((low_x-eps_cell)/cell_size))+1
        span_y = int(math.floor((high_y+eps_cell)/cell_size))-int(math.floor((low_y-eps_cell)/cell_size))+1
        span_z = int(math.floor((high_z+eps_cell)/cell_size))-int(math.floor((low_z-eps_cell)/cell_size))+1
        if span_x*span_y*span_z > 1_000_000:
            raise ValueError('cell size too small for triangle span; raise cell_size')
        for i in range(int(math.floor((low_x-eps_cell)/cell_size)),
                       int(math.floor((high_x+eps_cell)/cell_size))+1):
            for j in range(int(math.floor((low_y-eps_cell)/cell_size)),
                           int(math.floor((high_y+eps_cell)/cell_size))+1):
                for k in range(int(math.floor((low_z-eps_cell)/cell_size)),
                               int(math.floor((high_z+eps_cell)/cell_size))+1):
                    cells.setdefault((i, j, k), []).append(index)
    sets = [frozenset(row) for row in ids]
    n = len(triangles)
    pairs = []
    overflow = False
    total = 0
    seen = set()
    candidate = adjacent = tested = coplanar = 0
    for bucket in cells.values():
        m = len(bucket)
        if m < 2:
            continue
        for u in range(m-1):
            i = bucket[u]
            bi = boxes[i]
            vi = sets[i]
            ti = triangles[i]
            for v in range(u+1, m):
                j = bucket[v]
                key = i*n+j
                if key in seen:
                    continue
                seen.add(key)
                candidate += 1
                bj = boxes[j]
                if (bi[0] > bj[3] or bj[0] > bi[3] or bi[1] > bj[4]
                        or bj[1] > bi[4] or bi[2] > bj[5] or bj[2] > bi[5]):
                    continue
                if vi & sets[j]:
                    adjacent += 1
                    continue
                tested += 1
                if triangles_intersect(ti, triangles[j], eps):
                    total += 1
                    if len(pairs) < max_reported_pairs:
                        pairs.append((i, j))
                    overflow = True
    return dict(intersecting_pair_count=total,
                intersecting_pairs=pairs,
                reported_pairs_capped=overflow,
                candidate_pairs=candidate, adjacent_pairs_skipped=adjacent,
                tested_pairs=tested, cell_size_mm=cell_size,
                triangles=n,
                limitations=['pairs sharing a vertex (folds through a shared '
                             'vertex) are not classified',
                             'touching counts as intersection (conservative)'])
