"""Model-only shell export from G-code: helpers excluded, bands exact.

Collects planar extruding loops whose feature hint is an explicit WALL role
(external/overhang perimeter, perimeter, shells, outer wall); support, brim,
ironing, custom/prime, infill and unmarked paths never contribute boundary.
Seams close only within an explicit distance budget (added edge reported).
Per z level loops group into islands by containment; the outermost loop of
each island is its outline (holes are NOT inferred; inner wall passes are
counted and dropped). Consecutive levels with byte-identical island sets
merge into one prism run. One closed prism per island per run; stacked runs
occupy disjoint z bands, so the SUM of shell volumes is the exact enclosed
volume of the exported span. Internal transition caps between differing
outlines remain in the mesh (documented, never repaired). Centreline loops,
no bead width, never export-ready.
"""
import math
from pathlib import Path
import tempfile

from contour_context import feature_role
from contour_mesh import MAX_TRIANGLES, _inside, binary_stl, prism_mesh
from path_evidence import FEATURE
from r2_shadow import Shadow
from seam_reconstruction import close_planar_seam
from stl_audit import inspect_stl

WALL_HINTS = frozenset(('external perimeter', 'outer wall', 'wall-outer',
                        'perimeter', 'overhang perimeter', 'shells'))

MAX_LINE = 1024 * 1024
MAX_LOOPS = 8192


def _area(points):
    return abs(math.fsum(a[0]*b[1]-b[0]*a[1]
                         for a, b in zip(points, points[1:]+points[:1])))/2


def _islands(loops):
    """Group loops into islands: each loop joins the smallest loop containing it.

    Containment uses the loop's first vertex (strict interior, boundary
    contacts count as outside); the first member of each group is the
    outermost (largest-area) loop and becomes the island outline.
    """
    ordered = sorted(loops, key=lambda loop: -_area(loop['points_mm']))
    parent = list(range(len(ordered)))
    for index, loop in enumerate(ordered):
        host, host_area = None, None
        for outer in range(index):
            candidate = ordered[outer]
            area = _area(candidate['points_mm'])
            if _inside(loop['points_mm'][0], candidate['points_mm']):
                if host is None or area < host_area:
                    host, host_area = outer, area
        if host is not None:
            parent[index] = host
    roots = [index for index in range(len(ordered)) if parent[index] == index]
    groups = []
    for root in roots:
        members = [ordered[root]]
        members.extend(ordered[index] for index in range(len(ordered))
                       if index != root and parent[index] == root)
        groups.append(members)
    return groups


def model_shells(path, *, parser_options, seam_gap_mm, z_min_mm, z_max_mm):
    """Return (binary_stl_bytes, report) for the model shells of one z span."""
    if not (math.isfinite(seam_gap_mm) and seam_gap_mm >= 0):
        raise ValueError('finite nonnegative seam budget required')
    if not (math.isfinite(z_min_mm) and math.isfinite(z_max_mm) and z_max_mm > z_min_mm):
        raise ValueError('finite increasing z span required')
    state = Shadow(**dict(parser_options))
    hint = None
    chain = None
    chain_tool = None
    first_line = None
    filament = 0.0
    loops = []
    counts = dict(extruding_chains=0, wall_loops=0,
                  non_wall_role_paths=0,
                  seam_closed=0, seam_over_budget=0, vertex_budget_exceeded=0)

    def finish():
        nonlocal chain, chain_tool, first_line, filament
        if chain and len(chain) >= 3:
            counts['extruding_chains'] += 1
            if (hint or '').strip().lower() not in WALL_HINTS:
                counts['non_wall_role_paths'] += 1
            else:
                try:
                    proposal = close_planar_seam(chain, max_gap_mm=seam_gap_mm)
                except ValueError as exc:
                    if 'seam point budget' in str(exc):
                        counts['vertex_budget_exceeded'] += 1
                    else:
                        counts['seam_over_budget'] += 1
                else:
                    points = [(p[0], p[1]) for p in proposal['points_mm'][:-1]]
                    loops.append(dict(z_mm=chain[0][2], points_mm=points,
                                      hint=hint,
                                      role=feature_role(hint),
                                      added_edge_mm=proposal['added_edge_mm'],
                                      first_line=first_line,
                                      filament_mm=filament))
                    counts['wall_loops'] += 1
                    if proposal['added_edge_mm'] > 0:
                        counts['seam_closed'] += 1
        chain = None
        chain_tool = None
        first_line = None
        filament = 0.0

    with Path(path).open('r', encoding='utf-8', errors='surrogateescape', newline='') as source:
        number = 0
        while True:
            raw = source.readline(MAX_LINE+1)
            if not raw:
                break
            number += 1
            if len(raw) > MAX_LINE:
                raise ValueError('oversized input line; export refuses')
            record = state.process(raw, number)
            kind = record['kind']
            match = FEATURE.match(record.get('comment') or '')
            if match:
                new_hint = match.group(1) if match.group(1) is not None else match.group(2)
                if new_hint != hint:
                    finish()
                    hint = new_hint
            if kind == 'comment':
                continue
            if kind != 'move':
                finish()
                continue
            a, b = record['start_mm'], record['end_mm']
            de = record['commanded_e_delta_mm']
            if de is None or any(v is None for v in (*a.values(), *b.values())):
                finish()
                continue
            start = tuple(a[k] for k in 'XYZ')
            end = tuple(b[k] for k in 'XYZ')
            if de == 0 and start == end:
                continue
            if de <= 0 or start[:2] == end[:2]:
                finish()
                continue
            if start[2] != end[2]:
                finish()
                continue
            if not (z_min_mm < start[2] <= z_max_mm):
                finish()
                continue
            if chain and (chain[-1] != start or chain_tool != record['tool']):
                finish()
            if not chain:
                chain = [start]
                chain_tool = record['tool']
                first_line = number
            chain.append(end)
            filament += de
            if math.dist(end[:2], chain[0][:2]) == 0 and len(chain) >= 4:
                finish()
    finish()
    if len(loops) > MAX_LOOPS:
        raise ValueError('wall loop budget exceeded; narrow the z span')
    by_z = {}
    for loop in loops:
        by_z.setdefault(loop['z_mm'], []).append(loop)
    levels = sorted(by_z)
    if not levels:
        raise ValueError('no wall-role loops inside the requested z span')
    runs = []
    inner_dropped = 0
    for z in levels:
        islands = _islands(by_z[z])
        inner_dropped += sum(len(members)-1 for members in islands)
        outlines = sorted(tuple(members[0]['points_mm']) for members in islands)
        if runs and runs[-1]['outlines'] == outlines:
            runs[-1]['levels'].append(z)
        else:
            runs.append(dict(outlines=outlines, levels=[z]))
    triangles = []
    shell_reports = []
    for run_index, run in enumerate(runs):
        z_top = run['levels'][-1]
        z_bottom = (runs[run_index-1]['levels'][-1]
                    if run_index > 0 else z_min_mm)
        for outline in run['outlines']:
            mesh = prism_mesh(list(outline), z_bottom, z_top)
            if len(triangles)+len(mesh) > MAX_TRIANGLES:
                raise ValueError('triangle budget exceeded; narrow the z span')
            triangles.extend(mesh)
            shell_reports.append(dict(z_bottom_mm=z_bottom, z_top_mm=z_top,
                                      vertices=len(outline),
                                      volume_mm3=_area(outline)*(z_top-z_bottom)))
    data = binary_stl(triangles)
    with tempfile.TemporaryDirectory(prefix='r2-model-export-') as directory:
        stl_path = Path(directory)/'model.stl'
        stl_path.write_bytes(data)
        audit = inspect_stl(stl_path)
    for key in ('nonmanifold_edges', 'duplicate_faces', 'normal_errors',
                'winding_errors', 'degenerate_faces'):
        if audit[key]:
            raise ValueError('export failed mesh check: '+key)
    if audit['boundary_edges']:
        raise ValueError('exported shells must be closed')
    if audit['vertex_connected_components'] != len(shell_reports):
        raise ValueError('shell/component mismatch after export')
    return data, dict(schema='r2-model-shells/1', experimental=True,
                      export_ready=False,
                      parser_options=state.options_summary(),
                      z_span_mm=[z_min_mm, z_max_mm],
                      levels=len(levels), z_levels_mm=levels, runs=len(runs),
                      shells=len(shell_reports),
                      outline_changes=max(0, len(runs)-1),
                      transition_planes_mm=[runs[k-1]['levels'][-1]
                                            for k in range(1, len(runs))],
                      triangles=len(triangles),
                      total_volume_mm3=math.fsum(shell['volume_mm3']
                                                 for shell in shell_reports),
                      audit=audit,
                      counts=counts,
                      inner_wall_loops_dropped=inner_dropped,
                      seam_max_added_edge_mm=max((loop['added_edge_mm']
                                                  for loop in loops), default=0.0),
                      limitations=['wall hints only: support, brim, ironing, custom, '
                                  'infill and unmarked paths never contribute boundary',
                                  'holes are not inferred; inner wall passes are dropped',
                                  'internal transition caps between differing outlines '
                                  'remain in the mesh; volumes stay exact because z bands are disjoint',
                                  'centreline outlines; bead width not applied',
                                  'islands grouped by single-vertex containment; touching '
                                  'loops become separate islands'])
