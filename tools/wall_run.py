"""Stream a position-continuous vase wall run into per-revolution rings.

The sampler ingests extrusion paths one at a time (height never returns to an
earlier value, flat segments allowed, joins within an explicit gap budget),
keeps only a small sliding point buffer, and emits one ring per full pitch
band at N chord-interpolated sample heights. Flat rim loops contribute no
samples of their own.
Invalid rings (non-simple XY polygon) are recorded, not repaired. A wall
surface over the whole run is only built when EVERY ring validates.
"""
import math

from contour_mesh import _boundary
from ring_wall import ring_wall_mesh

MAX_BUFFER_POINTS = 4096
MAX_RUN_RINGS = 512


class WallRunSampler:
    """Streaming ring sampler for one ascending wall run."""

    def __init__(self, *, pitch_mm, samples_per_revolution, max_gap_mm=0.0):
        if not math.isfinite(pitch_mm) or pitch_mm <= 0:
            raise ValueError('positive finite pitch required')
        if type(samples_per_revolution) is not int or not 3 <= samples_per_revolution <= 256:
            raise ValueError('sample count per revolution must be an int in 3..256')
        if not math.isfinite(max_gap_mm) or max_gap_mm < 0:
            raise ValueError('finite nonnegative continuation budget required')
        self.pitch_mm=pitch_mm
        self.samples_per_revolution=samples_per_revolution
        self.max_gap_mm=max_gap_mm
        self.step_mm=pitch_mm/samples_per_revolution
        self.buffer=[]
        self.z_start=None
        self.cursor=0
        self.next_sample=0
        self.rings=[]
        self.rejected=[]
        self.joins=[]
        self.counts=dict(paths=0,points=0,shared_point_joins=0,bridged_joins=0,
                         dropped_incomplete_ring_samples=0)

    def _emit(self):
        step=self.step_mm
        z_max=self.buffer[-1][2]
        while self.z_start+self.next_sample*step < z_max:
            height=self.z_start+self.next_sample*step
            while (self.cursor+1 < len(self.buffer)
                   and self.buffer[self.cursor+1][2] <= height):
                self.cursor+=1
            if not (self.buffer[self.cursor][2] <= height
                    < self.buffer[self.cursor+1][2]):
                raise ValueError('query height without a covering segment')
            a,b=self.buffer[self.cursor],self.buffer[self.cursor+1]
            t=(height-a[2])/(b[2]-a[2])
            point=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]),height)
            band=self.next_sample//self.samples_per_revolution
            while len(self.rings) < band+1:
                self.rings.append([])
            self.rings[band].append(point)
            self.next_sample+=1
        floor=self.z_start+max(0,(self.next_sample-self.samples_per_revolution))*step
        cut=0
        while cut+1 < len(self.buffer) and self.buffer[cut+1][2] < floor:
            cut+=1
        if cut:
            del self.buffer[:cut]
            self.cursor-=cut
            if self.cursor < 0:
                self.cursor=0

    def add_path(self, points):
        points=[tuple(p) for p in points]
        if len(points) < 2:
            raise ValueError('each path needs at least two points')
        if any(len(p)!=3 or any(not math.isfinite(v) for v in p) for p in points):
            raise ValueError('finite XYZ points required')
        if any(a==b for a,b in zip(points,points[1:])):
            raise ValueError('duplicate consecutive points')
        if any(b[2] < a[2] for a,b in zip(points,points[1:])):
            raise ValueError('path height must never return to an earlier value')
        if not self.buffer:
            self.buffer=list(points)
            self.z_start=points[0][2]
        else:
            a,b=self.buffer[-1],points[0]
            if b[2] < a[2]:
                raise ValueError('continuation must not return to an earlier height')
            gap=math.dist(a,b)
            if gap > self.max_gap_mm:
                raise ValueError('continuation gap exceeds explicit budget')
            if gap == 0:
                self.joins.append('shared_point')
                self.counts['shared_point_joins']+=1
                self.buffer.extend(points[1:])
            else:
                self.joins.append('bridged_straight_segment')
                self.counts['bridged_joins']+=1
                self.buffer.extend(points)
        self.counts['paths']+=1
        self.counts['points']+=len(points)
        # Check the peak buffer size before pruning: one huge path must not
        # silently pass through memory it was never allowed to hold.
        if len(self.buffer) > MAX_BUFFER_POINTS:
            raise ValueError('sliding point buffer budget exceeded')
        self._emit()
        if len(self.rings) > MAX_RUN_RINGS:
            raise ValueError('run ring budget exceeded')

    def finish(self):
        rings=[]
        rejected=[]
        for index,ring in enumerate(self.rings):
            if len(ring)==self.samples_per_revolution:
                try:
                    _boundary([(x,y) for x,y,z in ring])
                except ValueError as exc:
                    rejected.append(dict(band_index=index,reason=str(exc)))
                    continue
                rings.append(dict(band_index=index,samples=len(ring),
                                  z_band_mm=[min(p[2] for p in ring),
                                             max(p[2] for p in ring)],
                                  points_mm=ring))
            elif ring:
                self.counts['dropped_incomplete_ring_samples']+=len(ring)
        return dict(rings=rings,rejected=rejected,joins=self.joins,
                    counts=dict(self.counts),
                    pitch_mm=self.pitch_mm,
                    samples_per_revolution=self.samples_per_revolution,
                    export_ready=False,
                    limitations=['chord interpolation; rings mix heights within one pitch band',
                                 'pitch equals one full XY revolution is a caller assumption',
                                 'rejected rings leave gaps; only contiguous ring spans may be stitched',
                                 'centreline rings; bead width not applied'])


def sample_wall_run(paths, *, pitch_mm, samples_per_revolution, max_gap_mm=0.0):
    sampler=WallRunSampler(pitch_mm=pitch_mm,
                           samples_per_revolution=samples_per_revolution,
                           max_gap_mm=max_gap_mm)
    for path in paths:
        sampler.add_path(path)
    return sampler.finish()


def wall_run_surface(paths, *, pitch_mm, samples_per_revolution, max_gap_mm=0.0):
    """Whole-run wall surface; refuses when any ring rejects validation."""
    sampled=sample_wall_run(paths,pitch_mm=pitch_mm,
                            samples_per_revolution=samples_per_revolution,
                            max_gap_mm=max_gap_mm)
    if sampled['rejected']:
        first=sampled['rejected'][0]
        raise ValueError('run rejected at band %d: %s'%(first['band_index'],
                                                        first['reason']))
    data,report=ring_wall_mesh(sampled['rings'])
    report['run_counts']=sampled['counts']
    report['pitch_mm']=pitch_mm
    report['samples_per_revolution']=samples_per_revolution
    return data,report
