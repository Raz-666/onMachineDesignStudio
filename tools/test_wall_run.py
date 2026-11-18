"""Streaming whole-run wall sampling: synthetic oracles plus the full Rose vase."""
import gzip
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from wall_run import sample_wall_run, wall_run_surface, MAX_BUFFER_POINTS
from r2_shadow import Shadow


def helix_run(revolutions=5, radius=10, pitch=1/16, segments=64):
    """One ascending helix split into per-revolution position-continuous paths."""
    points=[(radius*math.cos(2*math.pi*i/segments),
             radius*math.sin(2*math.pi*i/segments),
             pitch*i/segments) for i in range(revolutions*segments+1)]
    return [points[k*segments:(k+1)*segments+1] for k in range(revolutions)]


class WallRunTests(unittest.TestCase):
    def test_synthetic_run_rings_and_wall(self):
        paths=helix_run()
        sampled=sample_wall_run(paths,pitch_mm=1/16,samples_per_revolution=8)
        self.assertEqual(sampled['counts'],dict(paths=5,points=325,
                                                shared_point_joins=4,bridged_joins=0,
                                                dropped_incomplete_ring_samples=0))
        self.assertEqual(sampled['joins'],['shared_point']*4)
        self.assertEqual(sampled['rejected'],[])
        self.assertEqual([r['band_index'] for r in sampled['rings']],[0,1,2,3,4])
        for ring in sampled['rings']:
            self.assertEqual(ring['samples'],8)
        data,report=wall_run_surface(paths,pitch_mm=1/16,samples_per_revolution=8)
        self.assertEqual(report['triangles'],2*4*8)
        self.assertEqual(report['open_boundary_edges'],16)
        self.assertEqual(report['audit']['nonmanifold_edges'],0)
        self.assertFalse(report['export_ready'])

    def test_bridged_join_counted(self):
        paths=helix_run()
        # Shifting the LAST path bridges only its single inbound join.
        paths[-1]=[(x+.05,y,z) for x,y,z in paths[-1]]
        sampled=sample_wall_run(paths,pitch_mm=1/16,samples_per_revolution=8,max_gap_mm=.1)
        self.assertEqual(sampled['counts']['bridged_joins'],1)
        self.assertEqual(sampled['counts']['shared_point_joins'],3)
        self.assertEqual(len(sampled['rings']),5)

    def test_validation_rejections(self):
        paths=helix_run()
        cases=[([paths[0],[(x+1,y,z) for x,y,z in paths[1]]],{}),
               ([paths[0],[(x,y,z-.01) for x,y,z in paths[1]]],{}),
               (paths[::-1],{}),
               ([paths[0][:1]],{}),
               # One single path longer than the sliding buffer budget.
               ([[(10*math.cos(2*math.pi*i/64),10*math.sin(2*math.pi*i/64),(1/16)*i/64)
                  for i in range(100*64+1)]],{}),
               # More revolutions than the run ring budget.
               (helix_run(revolutions=520),{}),
               (paths,dict(pitch_mm=0)),
               (paths,dict(samples_per_revolution=8.0))]
        for run,kwargs in cases:
            with self.subTest(run=type(run),kwargs=kwargs),self.assertRaises(ValueError):
                sample_wall_run(run,pitch_mm=kwargs.get('pitch_mm',1/16),
                                samples_per_revolution=kwargs.get('samples_per_revolution',8))


class RealRoseFullWallTests(unittest.TestCase):
    def collect_run(self):
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
        return run

    def test_full_rose_vase_wall(self):
        run=self.collect_run()
        self.assertEqual(len(run),115)
        sampled=sample_wall_run(run,pitch_mm=.2,samples_per_revolution=96,max_gap_mm=.1)
        self.assertEqual(sampled['counts'],dict(paths=115,points=62916,
                                                shared_point_joins=114,bridged_joins=0,
                                                dropped_incomplete_ring_samples=0))
        self.assertEqual(sampled['rejected'],[])
        self.assertEqual(len(sampled['rings']),114)
        self.assertAlmostEqual(sampled['rings'][0]['z_band_mm'][0],1.2)
        self.assertAlmostEqual(sampled['rings'][-1]['z_band_mm'][1],24-.2/96)
        data,report=wall_run_surface(run,pitch_mm=.2,samples_per_revolution=96,max_gap_mm=.1)
        self.assertEqual(report['triangles'],21696)
        self.assertEqual(report['open_boundary_edges'],192)
        self.assertEqual(report['audit']['nonmanifold_edges'],0)
        self.assertEqual(report['audit']['winding_errors'],192)
        self.assertEqual(report['audit']['vertex_connected_components'],1)
        self.assertEqual(report['audit']['degenerate_faces'],0)
        self.assertGreater(report['audit']['signed_volume'],2600)
        self.assertLess(report['audit']['signed_volume'],2670)
        self.assertFalse(report['export_ready'])

    def test_coarse_sampling_rejects_bands_instead_of_repairing(self):
        run=self.collect_run()
        sampled=sample_wall_run(run,pitch_mm=.2,samples_per_revolution=64,max_gap_mm=.1)
        self.assertEqual(len(sampled['rings']),109)
        self.assertEqual([r['band_index'] for r in sampled['rejected']],[66,68,78,82,83])
        with self.assertRaises(ValueError):
            wall_run_surface(run,pitch_mm=.2,samples_per_revolution=64,max_gap_mm=.1)


if __name__ == '__main__':unittest.main(verbosity=2)
