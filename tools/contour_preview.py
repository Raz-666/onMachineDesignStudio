"""Explicit experimental prism previews from selected G-code seam proposals.

NOT the active exporter: selected planar simple centreline rings are extruded
through caller-supplied Z bounds. Neither object height nor hole membership is
inferred from G-code. No file is modified; this API returns bytes and provenance.
Multiple disjoint ring groups (islands) become separate closed shells.
"""
import math
from pathlib import Path
import tempfile

from physical_contours import offset_simple_centerline
from contour_mesh import prism_mesh, binary_stl, MAX_TRIANGLES
from stl_audit import inspect_stl

LIMITATIONS=['height and outer/hole selection supplied by caller, not recovered',
             'constant width, topology-preserving simple rings and miter corners only',
             'feature/object markers not geometrically verified',
             'islands must be separated by disjoint XY bounding boxes',
             'no original CAD recovery or independent slicer acceptance']


def _prepared(proposal, *, width_mm, role):
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
    offset=offset_simple_centerline([p[:2] for p in points],width_mm=width_mm,role=role)
    return dict(name=name,context=context,z=z,tool=proposal.get('tool'),offset=offset,
                source=dict(source_lines=proposal.get('source_lines'),object_context=context,
                            feature_hint=proposal.get('feature_hint'),
                            seam_operation=proposal.get('operation'),
                            added_edge_mm=proposal.get('added_edge_mm')))


def prism_set_preview(groups, *, width_mm, z_bottom, z_top):
    """Return (binary_stl_bytes, report) for one or more disjoint ring groups.

    groups: iterable of (outer_proposal, hole_proposals_sequence). All rings
    must share plane and tool; object markers may differ between groups.
    Islands are only accepted with pairwise disjoint XY bounding boxes.
    """
    groups=[(outer,list(holes)) for outer,holes in groups]
    if not groups:
        raise ValueError('at least one ring group required')
    prepared=[]
    plane=tool=None
    for outer,holes in groups:
        rings=[_prepared(outer,width_mm=width_mm,role='outer')]
        name=rings[0]['name']
        rings+=[_prepared(hole,width_mm=width_mm,role='hole') for hole in holes]
        for ring in rings:
            if plane is None:
                plane,tool=ring['z'],ring['tool']
            if (ring['z'],ring['tool']) != (plane,tool):
                raise ValueError('rings must share plane and tool')
            if ring['name'] != name:
                raise ValueError('rings of one group must share their object marker')
        prepared.append(rings)
    triangles=[]
    boxes=[]
    summaries=[]
    for rings in prepared:
        mesh=prism_mesh(rings[0]['offset']['points_mm'],z_bottom,z_top,
                        holes=[ring['offset']['points_mm'] for ring in rings[1:]])
        triangles+=mesh
        points=rings[0]['offset']['points_mm']
        boxes.append((min(p[0] for p in points),min(p[1] for p in points),
                      max(p[0] for p in points),max(p[1] for p in points)))
        summaries.append(dict(object_name=rings[0]['name'],tool=rings[0]['tool'],
                              sources=[ring['source'] for ring in rings],
                              offsets=[ring['offset'] for ring in rings]))
    if len(triangles) > MAX_TRIANGLES:
        raise ValueError('combined triangle budget exceeded')
    for i,(ax0,ay0,ax1,ay1) in enumerate(boxes):
        for bx0,by0,bx1,by1 in boxes[i+1:]:
            if not (ax1<bx0 or bx1<ax0 or ay1<by0 or by1<ay0):
                raise ValueError('ring groups overlap in XY bounding boxes')
    data=binary_stl(triangles)
    with tempfile.TemporaryDirectory(prefix='r2-preview-check-') as directory:
        path=Path(directory)/'preview.stl'
        path.write_bytes(data)
        audit=inspect_stl(path)
    for key in ('degenerate_faces','normal_errors','duplicate_faces','boundary_edges',
                'nonmanifold_edges','winding_errors'):
        if audit[key]:
            raise ValueError('preview failed mesh check: '+key)
    if audit['signed_volume']<=0 or audit['vertex_connected_components']!=len(groups):
        raise ValueError('preview must yield one positive-volume shell per group')
    return data,dict(schema='r2-prism-set-preview/1',experimental=True,export_ready=False,
                     object_names=[s['object_name'] for s in summaries],tool=tool,
                     source_plane_mm=plane,expected_components=len(groups),
                     explicit_parameters=dict(width_mm=width_mm,z_bottom=z_bottom,z_top=z_top),
                     groups=summaries,audit=audit,limitations=LIMITATIONS[:])


def prism_preview(outer, *, holes=(), width_mm, z_bottom, z_top):
    """Single-group compatibility view of prism_set_preview."""
    data,summary=prism_set_preview([(outer,list(holes))],width_mm=width_mm,
                                   z_bottom=z_bottom,z_top=z_top)
    flat=dict(summary)
    flat['schema']='r2-prism-preview/1'
    flat['object_name']=summary['groups'][0]['object_name']
    flat['sources']=[source for group in summary['groups'] for source in group['sources']]
    flat['offsets']=[offset for group in summary['groups'] for offset in group['offsets']]
    return data,flat


def _group_indices(report):
    proposals=report['path_evidence']['seam_policy']['proposals']
    def check(indices):
        if any(type(i) is not int or i<0 for i in indices):
            raise ValueError('distinct nonnegative proposal indices required')
        if len(set(indices))!=len(indices):
            raise ValueError('distinct nonnegative proposal indices required')
        if any(i>=len(proposals) for i in indices):
            raise ValueError('proposal index outside retained report')
    return proposals,check


def preview_from_report(report, *, outer_index=None, hole_indices=(), groups=None,
                        width_mm, z_bottom, z_top):
    """Select rings from ONE complete collector report (file-local IDs)."""
    if report.get('schema')!='r2-contour-candidates/1' or not report.get('complete_scan'):
        raise ValueError('complete contour-candidate report required')
    proposals,check=_group_indices(report)
    if groups is not None:
        if outer_index is not None:
            raise ValueError('pass either outer_index or groups, not both')
        selection=[(int(outer),[int(hole) for hole in hole_list]) for outer,hole_list in groups]
        if not selection:
            raise ValueError('at least one ring group required')
        check([i for pair in selection for i in [pair[0],*pair[1]]])
        data,summary=prism_set_preview([(proposals[outer],[proposals[i] for i in holes])
                                        for outer,holes in selection],
                                       width_mm=width_mm,z_bottom=z_bottom,z_top=z_top)
        summary['selection_indices']=selection
    else:
        if type(outer_index) is not int:
            raise ValueError('outer_index or groups required')
        indices=[outer_index,*hole_indices]
        check(indices)
        data,summary=prism_preview(proposals[outer_index],
                                   holes=[proposals[i] for i in hole_indices],
                                   width_mm=width_mm,z_bottom=z_bottom,z_top=z_top)
        summary['selection_indices']=indices
    summary['source']=report['source']
    summary['parser_options']=report['parser_options']
    return data,summary


def _parse_group(text):
    parts=text.split(':')
    if not 1 <= len(parts) <= 2 or not parts[0].strip():
        raise ValueError('group syntax OUTER[:HOLE,HOLE]')
    holes=[h for h in parts[1].split(',') if h.strip()] if len(parts)==2 else []
    try:
        return int(parts[0]),[int(h) for h in holes]
    except ValueError:
        raise ValueError('group syntax OUTER[:HOLE,HOLE]')


def main(argv=None):
    import argparse
    import json
    from gcode_contours import collect_contours
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gcode')
    parser.add_argument('--output',required=True,help='new .stl file; creates provenance .stl.json alongside')
    parser.add_argument('--outer-index',type=int)
    parser.add_argument('--hole-index',type=int,action='append',default=[])
    parser.add_argument('--group',action='append',default=[],
                        help='repeatable OUTER[:HOLE,HOLE] selection; replaces --outer-index')
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
    if args.group and args.outer_index is not None:
        parser.error('pass either --outer-index or --group, not both')
    try:
        groups=[_parse_group(text) for text in args.group]
    except ValueError as error:
        parser.error(str(error))
    report=collect_contours(args.gcode,klipper_passive=args.klipper_passive,seam_gap_mm=args.seam_gap_mm)
    if groups:
        data,summary=preview_from_report(report,groups=groups,width_mm=args.width_mm,
                                         z_bottom=args.z_bottom,z_top=args.z_top)
    else:
        data,summary=preview_from_report(report,outer_index=args.outer_index,
                                         hole_indices=args.hole_index,width_mm=args.width_mm,
                                         z_bottom=args.z_bottom,z_top=args.z_top)
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
