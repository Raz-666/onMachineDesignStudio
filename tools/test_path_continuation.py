"""Position-continuation joins: synthetic oracles plus a real Rose wall window."""
import gzip
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from path_continuation import joined_points
from spiral_rings import spiral_rings
from ring_wall import ring_wall_mesh
from r2_shadow import Shadow


def helix_path(radius, revolutions, pitch, *, start_z=0.0, start_angle=0.0, shift=0.0):
    points=[]
    for i in range(int(revolutions*48)+1):
        angle=start_angle+2*math.pi*i/48
        points.append((radius*math.cos(angle)+shift,radius*math.sin(angle)+shift,
                       start_z+pitch*i/48))
    return points


class ContinuationTests(unittest.TestCase):
    def test_shared_point_and_bridged_join(self):
        a=helix_path(10,2,1/16)
        b=helix_path(10,2,1/16,start_z=1/8,start_angle=4*math.pi)
        result=joined_points([a,b])
        self.assertEqual(result['path_count'],2)
        self.assertEqual(result['joins'],[dict(operation='shared_point',gap_mm=0.0,joined_index=97)])
        self.assertEqual(result['point_count'],97+96)
        shifted=[(x+.05,y,z) for x,y,z in b]
        result=joined_points([a,shifted],max_gap_mm=.1)
        join=result['joins'][0]
        self.assertEqual(join['operation'],'bridged_straight_segment')
        self.assertAlmostEqual(join['gap_mm'],.05)
        self.assertEqual(result['point_count'],97+97)
        self.assertFalse(result['export_ready'])

    def test_budget_gap_and_height_rejections(self):
        a=helix_path(5,1,1/16)
        higher=helix_path(5,1,1/16,start_z=1/16)
        lower=[(x,y,z-1/8) for x,y,z in higher]
        for paths,kwargs in (([a,higher],{}),
                             ([a,[(x+.5,y,z) for x,y,z in higher]],dict(max_gap_mm=.1)),
                             ([a,lower],dict(max_gap_mm=1.0)),
                             ([],{}),
                             ([[(0,0,0)]],{})):
            with self.subTest(paths=paths,kwargs=kwargs),self.assertRaises(ValueError):
                joined_points(paths,**kwargs)
        with self.assertRaises(ValueError):
            joined_points([helix_path(5,90,1/16),helix_path(5,90,1/16,start_z=90/16)])

    def test_real_rose_wall_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rose.gcode'
            with gzip.open('testfixtures/rose_215c_pla.gcode.gz','rb') as source, path.open('wb') as target:
                shutil.copyfileobj(source,target)
            state=Shadow(klipper_passive=True)
            window_start,window_end=13350,15390
            current=None
            paths=[]
            def finish():
                nonlocal current
                if current and current['points']:
                    paths.append(current['points'])
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
                        current=dict(end=start,tool=record['tool'],points=[])
                    current['end']=end
                    if window_start <= number <= window_end:
                        if not current['points']:
                            current['points'].append(start)
                        current['points'].append(end)
            finish()
        self.assertEqual(len(paths),5)
        joined=joined_points(paths,max_gap_mm=.1)
        self.assertEqual(joined['path_count'],5)
        self.assertEqual([j['operation'] for j in joined['joins']],
                         ['bridged_straight_segment','shared_point','shared_point','shared_point'])
        self.assertAlmostEqual(joined['joins'][0]['gap_mm'],.076922,places=5)
        rings=spiral_rings(joined['points_mm'],pitch_mm=.2,samples_per_revolution=64)
        self.assertEqual(rings['ring_count'],4)
        self.assertTrue(all(ring['samples']==64 for ring in rings['rings']))
        self.assertAlmostEqual(rings['rings'][0]['z_band_mm'][0],1.2)
        data,wall=ring_wall_mesh(rings['rings'])
        self.assertEqual(wall['triangles'],2*3*64)
        self.assertEqual(wall['open_boundary_edges'],128)
        self.assertEqual(wall['audit']['nonmanifold_edges'],0)
        self.assertFalse(wall['export_ready'])


if __name__ == '__main__':unittest.main(verbosity=2)
