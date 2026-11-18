"""Explicit experimental prism preview from selected G-code seam proposals.

NOT the active exporter: selected planar simple centreline rings are extruded
through caller-supplied Z bounds. Neither object height nor hole membership is
inferred from G-code. No file is modified; this API returns bytes and provenance.
"""
import math
from pathlib import Path
import tempfile

from physical_contours import offset_simple_centerline
from contour_mesh import prism_mesh, binary_stl
from stl_audit import inspect_stl


def prism_preview(outer, *, holes=(), width_mm, z_bottom, z_top):
    """Return (binary_stl_bytes, report) for a deliberately selected preview.

    Outer/hole selection and common constant width are explicit caller inputs.
    Reject helper/unclassified hints, missing/mixed object markers and differing
    planes/tools. A matching Outer wall hint is necessary but NOT verification.
    """
    proposals=[outer]+list(holes)
    object_name=None
    plane=None
    tool=None
    offsets=[]
    sources=[]
    for i,proposal in enumerate(proposals):
        if proposal.get('geometry') != 'nozzle_centerline':
            raise ValueError('centreline proposal required')
        if proposal.get('feature_role') != 'outer_wall_hint_unverified':
            raise ValueError('helper or unclassified feature cannot be used for preview')
        context=proposal.get('object_context',{})
        name=context.get('name')
        if not isinstance(name,str) or not name:
            raise ValueError('explicit source-file object marker required')
        points=proposal.get('points_mm',[])
        if len(points)<4 or tuple(points[0]) != tuple(points[-1]):
            raise ValueError('explicitly closed proposal required')
        if any(len(p)!=3 or any(not math.isfinite(v) for v in p) for p in points):
            raise ValueError('finite XYZ points required')
        z=points[0][2]
        if any(p[2]!=z for p in points):
            raise ValueError('planar proposal required')
        if i == 0:
            object_name,plane,tool=name,z,proposal.get('tool')
        elif (name,z,proposal.get('tool')) != (object_name,plane,tool):
            raise ValueError('rings must share object marker, plane and tool')
        offset=offset_simple_centerline([p[:2] for p in points],width_mm=width_mm,
                                       role='outer' if i==0 else 'hole')
        offsets.append(offset)
        sources.append(dict(source_lines=proposal.get('source_lines'),
                            object_context=context,feature_hint=proposal.get('feature_hint'),
                            seam_operation=proposal.get('operation'),
                            added_edge_mm=proposal.get('added_edge_mm')))
    # prism_mesh validates nesting and ring intersections after offsets.
    triangles=prism_mesh(offsets[0]['points_mm'],z_bottom,z_top,
                         holes=[o['points_mm'] for o in offsets[1:]])
    data=binary_stl(triangles)
    with tempfile.TemporaryDirectory(prefix='r2-preview-check-') as directory:
        path=Path(directory)/'preview.stl'
        path.write_bytes(data)
        audit=inspect_stl(path)
    for key in ('degenerate_faces','normal_errors','duplicate_faces','boundary_edges',
                'nonmanifold_edges','winding_errors'):
        if audit[key]:
            raise ValueError('preview failed mesh check: '+key)
    if audit['signed_volume']<=0 or audit['vertex_connected_components']!=1:
        raise ValueError('preview must be a single positive-volume surface')
    return data,dict(schema='r2-prism-preview/1',experimental=True,export_ready=False,
                     object_name=object_name,tool=tool,source_plane_mm=plane,
                     explicit_parameters=dict(width_mm=width_mm,z_bottom=z_bottom,z_top=z_top),
                     sources=sources,offsets=offsets,audit=audit,
                     limitations=['height and outer/hole selection supplied by caller, not recovered',
                                  'constant width, topology-preserving simple rings and miter corners only',
                                  'feature/object markers not geometrically verified',
                                  'no original CAD recovery or independent slicer acceptance'])


def preview_from_report(report, *, outer_index, hole_indices=(), width_mm, z_bottom, z_top):
    """Select all rings from ONE complete collector report (file-local IDs)."""
    if report.get('schema')!='r2-contour-candidates/1' or not report.get('complete_scan'):
        raise ValueError('complete contour-candidate report required')
    indices=[outer_index]+list(hole_indices)
    if any(type(i) is not int or i<0 for i in indices) or len(set(indices))!=len(indices):
        raise ValueError('distinct nonnegative proposal indices required')
    proposals=report['path_evidence']['seam_policy']['proposals']
    if any(i>=len(proposals) for i in indices):
        raise ValueError('proposal index outside retained report')
    data,summary=prism_preview(proposals[outer_index],holes=[proposals[i] for i in hole_indices],
                               width_mm=width_mm,z_bottom=z_bottom,z_top=z_top)
    summary['source']=report['source']
    summary['parser_options']=report['parser_options']
    summary['selection_indices']=indices
    return data,summary


def main(argv=None):
    import argparse
    import json
    from gcode_contours import collect_contours
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gcode')
    parser.add_argument('--output',required=True,help='new .stl file; creates provenance .stl.json alongside')
    parser.add_argument('--outer-index',type=int,required=True)
    parser.add_argument('--hole-index',type=int,action='append',default=[])
    parser.add_argument('--width-mm',type=float,required=True)
    parser.add_argument('--z-bottom',type=float,required=True)
    parser.add_argument('--z-top',type=float,required=True)
    parser.add_argument('--seam-gap-mm',type=float,required=True)
    parser.add_argument('--klipper-passive',action='store_true')
    args=parser.parse_args(argv)
    output=Path(args.output)
    sidecar=Path(str(output)+'.json')
    if output.suffix.lower()!='.stl':
        parser.error('output must be a new .stl file')
    if output.exists() or sidecar.exists():
        parser.error('output or provenance sidecar already exists; refusing overwrite')
    report=collect_contours(args.gcode,klipper_passive=args.klipper_passive,seam_gap_mm=args.seam_gap_mm)
    data,summary=preview_from_report(report,outer_index=args.outer_index,hole_indices=args.hole_index,
                                    width_mm=args.width_mm,z_bottom=args.z_bottom,z_top=args.z_top)
    text=json.dumps(summary,indent=2,allow_nan=False)+'\n'
    created=[]
    try:
        with output.open('xb') as stream:
            created.append(output)
            stream.write(data)
        with sidecar.open('x',encoding='utf-8') as stream:
            created.append(sidecar)
            stream.write(text)
    except Exception:
        for path in created:
            path.unlink()
        raise
    print('Experimental prism preview (not release-approved):',output)
    print('Assumptions and audit:',sidecar)


if __name__ == '__main__':main()
