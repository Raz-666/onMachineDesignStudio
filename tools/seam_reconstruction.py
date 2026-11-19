"""Explicit planar centreline seam proposals; never physical contours or STL.

Only the missing straight closing edge may be added. Existing vertices are
unchanged. Nonplanar paths, oversized gaps and invalid polygons are rejected.
"""
import math
from contour_mesh import _boundary, MAX_VERTICES


def close_planar_seam(points, *, max_gap_mm):
    if not math.isfinite(max_gap_mm) or max_gap_mm < 0:
        raise ValueError('finite nonnegative seam budget required')
    if not 3 <= len(points) <= MAX_VERTICES + 1:
        raise ValueError('seam point budget exceeded or insufficient points')
    if any(len(p) != 3 or any(not math.isfinite(v) for v in p) for p in points):
        raise ValueError('finite XYZ points required')
    original = [tuple(p) for p in points]
    if any(p[2] != original[0][2] for p in original):
        raise ValueError('nonplanar path requires separate reconstruction')
    gap = math.dist(original[0][:2],original[-1][:2])
    if gap > max_gap_mm:
        raise ValueError('seam exceeds explicit distance budget')
    # Validation checks the new closing edge too; do not silently reorder points.
    _boundary([p[:2] for p in original])
    closed = original if gap == 0 else original + [original[0]]
    return dict(points_mm=closed, geometry='nozzle_centerline', export_ready=False,
                operation='none' if gap == 0 else 'add_straight_closing_edge',
                added_edge_mm=gap, max_gap_mm=max_gap_mm,
                max_existing_vertex_displacement_mm=0.0,
                limitation='closing segment is an explicit approximation, not recovered CAD geometry')
