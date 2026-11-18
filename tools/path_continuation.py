"""Explicit position-continuation joins between extrusion path point sets.

Real vase-mode walls are split into several extrusion paths by marker commands,
E resets or feed-only moves, while the nozzle position stays continuous. This
module joins such paths into one point sequence under an explicit gap budget:
an exactly shared point is reused, a small gap becomes a recorded straight
bridge segment (an explicit approximation, not recorded motion). Height must
never return to an earlier value. Never export-ready.
"""
import math

MAX_JOINED_POINTS = 8192


def joined_points(paths, *, max_gap_mm=0.0, max_points=MAX_JOINED_POINTS):
    """Join position-continuous paths; returns points plus join provenance."""
    paths=[list(path) for path in paths]
    if not paths:
        raise ValueError('at least one path required')
    if not math.isfinite(max_gap_mm) or max_gap_mm < 0:
        raise ValueError('finite nonnegative continuation budget required')
    if type(max_points) is not int or max_points < 3:
        raise ValueError('integer joined point budget of at least 3 required')
    joined=[]
    for path in paths:
        if len(path) < 2:
            raise ValueError('each path needs at least two points')
        if any(len(p)!=3 or any(not math.isfinite(v) for v in p) for p in path):
            raise ValueError('finite XYZ points required')
        if not joined:
            joined=list(path)
            continue
        a,b=joined[-1],path[0]
        if b[2] < a[2]:
            raise ValueError('continuation must not return to an earlier height')
        gap=math.dist(a,b)
        if gap > max_gap_mm:
            raise ValueError('continuation gap exceeds explicit budget')
        if gap == 0:
            joined.extend(path[1:])
        else:
            joined.extend(path)
    if len(joined) > max_points:
        raise ValueError('joined point budget exceeded')
    if any(a==b for a,b in zip(joined,joined[1:])):
        raise ValueError('duplicate consecutive points')
    joins=[]
    consumed=0
    previous_end=None
    for path in paths:
        if previous_end is not None:
            gap=math.dist(previous_end,path[0])
            joins.append(dict(operation='shared_point' if gap==0 else 'bridged_straight_segment',
                              gap_mm=gap,
                              joined_index=consumed))
        previous_end=path[-1]
        consumed+=len(path)
    return dict(points_mm=joined,joins=joins,path_count=len(paths),
                point_count=len(joined),max_gap_mm=max_gap_mm,
                export_ready=False,
                limitations=['straight bridges are explicit approximations, not recorded motion',
                             'continuity is measured between caller-supplied path endpoints only',
                             'paths must already be ordered along the wall'])
