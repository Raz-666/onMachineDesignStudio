"""Read-only bridge from r2_shadow normalized moves to exact planar path loops.

Diagnostic only: centreline loops are NOT physical contours. No STL output,
feature inference, endpoint snapping, layer merging, or guessed initial state.
Explicit --seam-gap-mm may propose a bounded closing edge for planar paths only.
Unknown semantics, arcs and nonplanar extrusion break chains and are reported.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from r2_shadow import Shadow
from path_evidence import PathEvidence
from contour_mesh import _boundary, MAX_VERTICES

MAX_LOOPS = 1024
MAX_LINE = 1024 * 1024
MAX_LINES = 2000000


def collect_contours(path, *, klipper_passive=False, seam_gap_mm=None,
                     assumed_layer_height_mm=None, filament_diameter_mm=1.75,
                     retain_nonplanar_points=False):
    # Reuse the existing explicit dialect capability; never assume initial state.
    state = Shadow(klipper_passive=klipper_passive)
    paths = PathEvidence(seam_gap_mm=seam_gap_mm,
                         assumed_layer_height_mm=assumed_layer_height_mm,
                         filament_diameter_mm=filament_diameter_mm,
                         retain_nonplanar_points=retain_nonplanar_points)
    loops, issues = [], Counter()
    unknown_examples = []
    chain = []
    first_line = last_line = None
    filament = 0.0
    tool = None
    truncated = False

    def flush():
        nonlocal chain, filament, first_line, last_line, tool
        if chain:
            issues['open_extrusion_chains'] += 1
        chain = []
        filament = 0.0
        first_line = last_line = tool = None

    # Bounded readline: an oversized line is refused, never truncated and parsed.
    with Path(path).open('r', encoding='utf-8', errors='surrogateescape', newline='') as source:
        number = 0
        while True:
            raw = source.readline(MAX_LINE+1)
            if not raw:
                break
            number += 1
            if len(raw) > MAX_LINE or number > MAX_LINES:
                issues['input_budget_exceeded'] += 1
                truncated = True
                break
            record = state.process(raw,number)
            paths.consume(record)
            kind = record['kind']
            if kind == 'comment':
                continue
            if kind != 'move':
                flush()
                if kind == 'unknown':
                    issues['unknown_records'] += 1
                    if len(unknown_examples) < 8:
                        unknown_examples.append(dict(line=number, reason=record.get('reason', 'unknown')))
                elif kind == 'arc':
                    issues['unsupported_arcs'] += 1
                continue
            a,b = record['start_mm'],record['end_mm']
            de = record['commanded_e_delta_mm']
            if de is None or any(v is None for v in (*a.values(),*b.values())):
                flush()
                issues['unknown_motion_state'] += 1
                continue
            start,end = tuple(a[k] for k in 'XYZ'),tuple(b[k] for k in 'XYZ')
            if not all(math.isfinite(v) for v in (*start,*end,de)):
                flush()
                issues['nonfinite_motion'] += 1
                continue
            if de == 0 and start == end:
                # Feed-only and duplicate-position moves do not break a path.
                continue
            if de <= 0 or start[:2] == end[:2]:
                flush()
                continue
            if start[2] != end[2]:
                flush()
                issues['nonplanar_extrusion'] += 1
                continue
            if chain and (chain[-1] != start or tool != record['tool']):
                flush()
            if not chain:
                chain = [start]
                first_line = number
                tool = record['tool']
            chain.append(end)
            filament += de
            last_line = number
            if end == chain[0] and len(chain) >= 4:
                points = [p[:2] for p in chain[:-1]]
                try:
                    _boundary(points)  # validation only, preserve original order/coordinates
                except ValueError:
                    issues['invalid_closed_contours'] += 1
                else:
                    loops.append(dict(z_mm=start[2], points_mm=points,
                                      source_lines=[first_line,last_line], tool=tool,
                                      commanded_filament_mm=filament,
                                      geometry='nozzle_centerline', classification='UNKNOWN'))
                chain = []
                filament = 0.0
                if len(loops) >= MAX_LOOPS:
                    issues['loop_budget_reached'] += 1
                    truncated = True
                    break
            elif len(chain) > MAX_VERTICES:
                flush()
                issues['contour_vertex_budget_exceeded'] += 1
    flush()
    paths.finish('scan_budget' if truncated else 'eof')
    return dict(schema='r2-contour-candidates/1', source=str(path),
                complete_scan=not truncated, export_ready=False,
                parser_options=state.options_summary(), path_evidence=paths.report(),
                loops=loops, diagnostics=dict(issues), unknown_examples=unknown_examples,
                limitations=['centreline only; physical width/offset missing',
                             'closed loops may be skirt, support, infill or walls',
                             'exact closure only; no seam snapping',
                             'no object/hole/layer correspondence inferred',
                             'coordinates are shadow command frame, not verified machine geometry',
                             'no macro execution; optional Klipper passive semantics explicitly recorded'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gcode', help='uncompressed G-code; input is read-only')
    parser.add_argument('--klipper-passive', action='store_true',
                        help='opt in to the shadow parser Klipper non-motion command model; no initial-state guesses')
    parser.add_argument('--seam-gap-mm', type=float, default=None,
                        help='opt-in planar seam proposals with explicit maximum added edge; never STL')
    parser.add_argument('--assume-layer-height-mm', type=float, default=None,
                        help='explicit unverified assumption for stadium width estimates; measured=False')
    parser.add_argument('--filament-diameter-mm', type=float, default=1.75,
                        help='filament diameter used with --assume-layer-height-mm')
    parser.add_argument('--retain-nonplanar-points', action='store_true',
                        help='keep points of the longest nonplanar paths (bounded) for spiral ring sampling')
    args = parser.parse_args()
    print(json.dumps(collect_contours(args.gcode, klipper_passive=args.klipper_passive,
                                      seam_gap_mm=args.seam_gap_mm,
                                      assumed_layer_height_mm=args.assume_layer_height_mm,
                                      filament_diameter_mm=args.filament_diameter_mm,
                                      retain_nonplanar_points=args.retain_nonplanar_points),indent=2,ensure_ascii=True))
