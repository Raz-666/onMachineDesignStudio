"""Evidence-based bead width for whole chained extrusion runs.

collect_chained_run reads a G-code file once and chains position-continuous
extruding paths from a caller-supplied first move line (object evidence
decides where the run starts). run_width_evidence turns per-path commanded
filament and length into stadium-section width estimates. wall_width_audit
applies a candidate uniform width to sampled rings on both sides and
reports acceptance per side WITHOUT raising: rejection counts are results,
not errors. All estimates, never measurements; never export-ready.
"""
import math
import statistics
from pathlib import Path

from physical_contours import width_from_filament
from r2_shadow import Shadow
from wall_surfaces import offset_wall_rings


def collect_chained_run(path, *, first_line, max_join_gap_mm=0.1):
    """Return (paths, filament_mm, length_mm) for one chained extrusion run.

    Paths are maximal position-continuous sequences of extruding XY moves;
    retractions, Z-only moves and non-motion records break a path. A path
    that STARTED before first_line is dropped entirely, even when it extends
    past it. The chain ends at the first join gap above max_join_gap_mm.
    """
    if not (isinstance(first_line,int) and first_line >= 1):
        raise ValueError('first move line must be a positive integer')
    if not (math.isfinite(max_join_gap_mm) and max_join_gap_mm > 0):
        raise ValueError('positive finite join gap required')
    path=Path(path)
    current=None
    collected=[]
    def finish():
        nonlocal current
        if current and current['points']:
            collected.append(current)
        current=None
    state=Shadow(klipper_passive=True)
    with path.open('r',encoding='utf-8',errors='surrogateescape',newline='') as source:
        number=0
        while True:
            raw=source.readline(1024*1024+1)
            if not raw:
                break
            number+=1
            record=state.process(raw,number)
            kind=record['kind']
            if kind not in ('move','comment','non_motion_event'):
                finish()
                continue
            if kind!='move':
                continue
            a,b=record['start_mm'],record['end_mm']
            start=tuple(a[k] for k in 'XYZ')
            end=tuple(b[k] for k in 'XYZ')
            de=record['commanded_e_delta_mm']
            if any(v is None for v in (*start,*end,de)):
                finish()
                continue
            if de==0 and start==end:
                continue
            if de<=0 or start[:2]==end[:2]:
                finish()
                continue
            if current and (current['end']!=start or current['tool']!=record['tool']):
                finish()
            if current is None:
                current=dict(end=start,tool=record['tool'],first=number,
                             points=[start] if number>=first_line else [])
                if number<first_line:
                    current['skip']=True
            current['end']=end
            if not current.get('skip'):
                current['points'].append(end)
                current['filament_mm']=current.get('filament_mm',0.0)+de
                current['length_mm']=current.get('length_mm',0.0)+math.dist(start,end)
    finish()
    paths=[];filaments=[];lengths=[];previous=None
    for item in collected:
        if item.get('skip') or not item['points']:
            continue
        if previous is not None and math.dist(previous,item['points'][0])>max_join_gap_mm:
            break
        paths.append(item['points'])
        filaments.append(item['filament_mm'])
        lengths.append(item['length_mm'])
        previous=paths[-1][-1]
    return paths,filaments,lengths


def run_width_evidence(filament_mm, length_mm, *, layer_height_mm,
                       filament_diameter_mm=1.75):
    """Per-path stadium width estimates plus aggregate evidence."""
    filament_mm=list(filament_mm)
    length_mm=list(length_mm)
    if not filament_mm or len(filament_mm)!=len(length_mm):
        raise ValueError('parallel non-empty filament and length lists required')
    if any(not math.isfinite(v) or v<=0 for v in filament_mm+length_mm):
        raise ValueError('positive finite per-path filament and length required')
    if not (math.isfinite(layer_height_mm) and layer_height_mm>0):
        raise ValueError('positive finite layer height required')
    if not (math.isfinite(filament_diameter_mm) and filament_diameter_mm>0):
        raise ValueError('positive finite filament diameter required')
    widths=[]
    unsupported=[]
    for index,(filament,length) in enumerate(zip(filament_mm,length_mm)):
        try:
            widths.append(width_from_filament(filament_mm=filament,
                                              path_length_mm=length,
                                              layer_height_mm=layer_height_mm,
                                              filament_diameter_mm=filament_diameter_mm)['width_mm'])
        except ValueError:
            widths.append(None)
            unsupported.append(index)
    estimated=[w for w in widths if w is not None]
    area=math.pi*filament_diameter_mm**2/4
    return dict(paths=len(filament_mm),
                width_mm=widths,
                unsupported_indices=unsupported,
                estimated_paths=len(estimated),
                min_mm=min(estimated) if estimated else None,
                median_mm=statistics.median(estimated) if estimated else None,
                max_mm=max(estimated) if estimated else None,
                commanded_filament_mm=math.fsum(filament_mm),
                commanded_volume_mm3=math.fsum(filament_mm)*area,
                model='stadium section per path (width_from_filament); estimate, not a measurement',
                assumptions='effective commanded filament-mm; constant layer height; no M221/PA/volumetric corrections')


def wall_width_audit(rings, *, width_mm):
    """Apply one uniform width to every ring on both sides; report, never raise."""
    rings=list(rings)
    if not rings:
        raise ValueError('non-empty rings required')
    if not (math.isfinite(width_mm) and width_mm>0):
        raise ValueError('positive finite width required')
    band_index={tuple(ring['z_band_mm']):i for i,ring in enumerate(rings)}
    sides={}
    for side in ('outer','inner'):
        _,rejections=offset_wall_rings(rings,width_mm=width_mm,side=side)
        indices=[]
        reasons={}
        for rejection in rejections:
            indices.append(band_index[tuple(rejection['z_band_mm'])])
            reasons[rejection['reason']]=reasons.get(rejection['reason'],0)+1
        sides[side]=dict(accepted=len(rings)-len(rejections),
                         rejected=len(rejections),
                         rejected_ring_indices=sorted(indices),
                         rejection_reasons=reasons,
                         first_reason=rejections[0]['reason'] if rejections else None)
    return dict(width_mm=width_mm,rings=len(rings),
                outer=sides['outer'],inner=sides['inner'],
                join='vertex_normal',
                limitations=['constant width applied to every ring',
                             'vertex-normal join; vertical bead sides; spiral tilt not corrected',
                             'rejections are results: a rejecting ring is documented, not repaired'])
