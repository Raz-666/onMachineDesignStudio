"""Closed vase surfaces: cylinder oracle, full Rose closure, rim agreement."""
import gzip
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from wall_run import sample_wall_run
from vase_closure import close_vase_surface, rim_agreement
from r2_shadow import Shadow


def helix_run(revolutions=5, radius=10, pitch=1/16, segments=64):
    points=[(radius*math.cos(2*math.pi*i/segments),
             radius*math.sin(2*math.pi*i/segments),
             pitch*i/segments) for i in range(revolutions*segments+1)]
    return [points[k*segments:(k+1)*segments+1] for k in range(revolutions)]


_RUN_CACHE=None


def rose_run():
    global _RUN_CACHE
    if _RUN_CACHE is not None:
        return _RUN_CACHE
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rose.gcode'
        with gzip.open('testfixtures/rose_215c_pla.gcode.gz','rb') as source, path.open('wb') as target:
            shutil.copyfileobj(source,target)
        state=Shadow(klipper_passive=True)
        current=None
        paths=[]
        def finish():
            nonlocal current
            if current and current['points']:
                paths.append((current['first'],current['points']))
            current=None
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
                                 points=[start] if number>=13404 else [])
                current['end']=end
                if number>=13404:
                    current['points'].append(end)
        finish()
    run=[]
    previous=None
    for first,points in paths:
        if first<13404:
            continue
        if previous is not None and math.dist(previous,points[0])>.1:
            break
        run.append(points)
        previous=points[-1]
    _RUN_CACHE=run
    return run


class ClosureTests(unittest.TestCase):
    def test_cylinder_volume_oracle(self):
        rings=sample_wall_run(helix_run(),pitch_mm=1/16,samples_per_revolution=8)['rings']
        data,report=close_vase_surface(rings,bottom_z=0,top_z=5/16)
        xy=[(p[0],p[1]) for p in rings[0]['points_mm']]
        area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(xy,xy[1:]+xy[:1])))/2
        # Cavalieri: congruent rotated sections give exactly area * height.
        self.assertAlmostEqual(report['audit']['signed_volume'],area*(5/16),places=6)
        audit=report['audit']
        self.assertEqual(audit['boundary_edges'],0)
        self.assertEqual(audit['nonmanifold_edges'],0)
        self.assertEqual(audit['winding_errors'],0)
        self.assertEqual(audit['vertex_connected_components'],1)
        self.assertEqual(report['triangles'],106)
        self.assertEqual(report['caps']['bottom_collapsed_strip_triangles'],2)
        self.assertEqual(report['caps']['top_collapsed_strip_triangles'],0)
        self.assertFalse(report['export_ready'])

    def test_cap_plane_validation(self):
        rings=sample_wall_run(helix_run(),pitch_mm=1/16,samples_per_revolution=8)['rings']
        for kwargs in (dict(bottom_z=.01,top_z=5/16),
                       dict(bottom_z=0,top_z=.3),
                       dict(bottom_z=float('nan'),top_z=5/16),
                       dict(bottom_z=1,top_z=0)):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                close_vase_surface(rings,**kwargs)
        with self.assertRaises(ValueError):
            close_vase_surface(rings[:1],bottom_z=0,top_z=5/16)


class RealRoseClosedTests(unittest.TestCase):
    def test_full_rose_closed_surface(self):
        run=rose_run()
        sampled=sample_wall_run(run,pitch_mm=.2,samples_per_revolution=96,max_gap_mm=.1)
        data,report=close_vase_surface(sampled['rings'],bottom_z=1.2,top_z=24.0)
        audit=report['audit']
        self.assertEqual(report['triangles'],22266)
        self.assertEqual(audit['boundary_edges'],0)
        self.assertEqual(audit['nonmanifold_edges'],0)
        self.assertEqual(audit['winding_errors'],0)
        self.assertEqual(audit['duplicate_faces'],0)
        self.assertEqual(audit['degenerate_faces'],0)
        self.assertEqual(audit['vertex_connected_components'],1)
        self.assertAlmostEqual(audit['signed_volume'],4810.105276,places=3)
        self.assertAlmostEqual(report['caps']['bottom_max_vertical_deviation_mm'],
                               .19791666666666674)
        self.assertAlmostEqual(report['caps']['top_max_vertical_deviation_mm'],.2)
        self.assertEqual(report['caps']['bottom_collapsed_strip_triangles'],2)
        self.assertEqual(report['caps']['top_collapsed_strip_triangles'],0)
        self.assertFalse(report['export_ready'])

    def test_full_rose_rim_agreement(self):
        run=rose_run()
        sampled=sample_wall_run(run,pitch_mm=.2,samples_per_revolution=96,max_gap_mm=.1)
        agreement=rim_agreement(sampled['rings'][-1],run[-1])
        self.assertEqual(agreement['ring_vertices'],96)
        self.assertEqual(agreement['rim_vertices'],512)
        self.assertAlmostEqual(agreement['ring_area_mm2'],274.490283,places=4)
        self.assertAlmostEqual(agreement['rim_area_mm2'],277.080784,places=4)
        self.assertAlmostEqual(agreement['area_difference_mm2'],2.590501,places=4)
        # Every flattened ring vertex lies on the recorded rim polyline
        # to within float noise (dev print rounds to 0.0).
        self.assertLessEqual(agreement['max_distance_mm'],1e-9)
        self.assertLessEqual(agreement['mean_distance_mm'],1e-9)


if __name__ == '__main__':unittest.main(verbosity=2)
