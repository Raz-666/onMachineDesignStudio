"""Width application to wall rings: analytic oracles plus the real Rose span."""
import gzip
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from physical_contours import vertex_normal_offset
from wall_surfaces import offset_wall_rings, wall_surface
from spiral_rings import spiral_rings
from r2_shadow import Shadow
from path_continuation import joined_points


def circle_ring(radius=10, samples=64, z_step=.001, z_offset=0.0):
    points=[(radius*math.cos(2*math.pi*i/samples),
             radius*math.sin(2*math.pi*i/samples),
             z_offset+z_step*i) for i in range(samples)]
    return dict(samples=samples,
                z_band_mm=[z_offset,z_offset+z_step*(samples-1)],
                points_mm=points)


class VertexOffsetTests(unittest.TestCase):
    def test_circle_is_exact_and_z_survives(self):
        ring=circle_ring()
        for side,expected in (('outer',10.2),('hole',9.8)):
            result=vertex_normal_offset([(p[0],p[1]) for p in ring['points_mm']],
                                        width_mm=.4,role=side)
            for (x,y) in result['points_mm']:
                self.assertAlmostEqual(math.hypot(x,y),expected,places=9)
        outer=offset_wall_rings([ring],width_mm=.4,side='outer')[0][0]
        for (x,y,z),(_,_,original_z) in zip(outer['points_mm'],ring['points_mm']):
            self.assertEqual(z,original_z)
            self.assertAlmostEqual(math.hypot(x,y),10.2,places=9)

    def test_square_corner_deviation_is_bounded_and_documented(self):
        square=[(0,0),(1,0),(1,1),(0,1)]
        result=vertex_normal_offset(square,width_mm=.4,role='outer')
        # Every vertex of a square is a corner: each moves along its diagonal
        # vertex normal by w/2, so corner-adjacent edges shift by w/(2*sqrt(2))
        # instead of w/2. The exact miter corner would be (1.2, 1.2).
        corner=result['points_mm'][2]
        self.assertAlmostEqual(corner[0],1+0.2/math.sqrt(2))
        self.assertAlmostEqual(corner[1],1+0.2/math.sqrt(2))
        self.assertAlmostEqual(result['points_mm'][1][1],-0.2/math.sqrt(2))
        self.assertIn('deviate',result['deviation_note'])

    def test_unstable_and_flipping_corners_rejected(self):
        # Path nearly doubles back on itself: invalid or unstable under offset.
        needle=[(0,0),(1,0),(0,.001),(.3,.5)]
        with self.assertRaises(ValueError):
            vertex_normal_offset(needle,width_mm=.4,role='outer')
        # A sharp inward tip flips its corner orientation at width 2.
        spike=[(0,0),(10,0),(10,6),(5,5.9),(0,6)]
        with self.assertRaises(ValueError):
            vertex_normal_offset(spike,width_mm=2,role='outer')
        with self.assertRaises(ValueError):
            vertex_normal_offset([(0,0),(1,0),(1,1)],width_mm=0,role='outer')
        with self.assertRaises(ValueError):
            vertex_normal_offset([(0,0),(1,0),(1,1)],width_mm=.4,role='wall')

    def test_offset_cylinder_wall_surface(self):
        rings=[circle_ring(10,32,.001,z_offset=.1*i) for i in range(4)]
        data,report=wall_surface(rings,width_mm=.4,side='outer')
        self.assertEqual(report['triangles'],2*3*32)
        self.assertEqual(report['open_boundary_edges'],64)
        self.assertEqual(report['audit']['nonmanifold_edges'],0)
        self.assertEqual(report['side'],'outer')
        self.assertFalse(report['export_ready'])


class RealRoseTests(unittest.TestCase):
    def collect_window_rings(self):
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
                    if 13350 <= number <= 15390:
                        if not current['points']:
                            current['points'].append(start)
                        current['points'].append(end)
            finish()
        joined=joined_points(paths,max_gap_mm=.1)
        return spiral_rings(joined['points_mm'],pitch_mm=.2,samples_per_revolution=64)['rings']

    def test_real_rose_width_threshold(self):
        rings=self.collect_window_rings()
        self.assertEqual(len(rings),4)
        # Up to 0.24 mm every ring keeps its topology; larger plausible
        # widths are rejected at the petal notches. This is measured
        # evidence, NOT a verified bead width.
        outer,rejections=offset_wall_rings(rings,width_mm=.24,side='outer')
        self.assertEqual(len(outer),4)
        self.assertEqual(rejections,[])
        data,report=wall_surface(rings,width_mm=.24,side='outer')
        self.assertEqual(report['triangles'],384)
        self.assertEqual(report['open_boundary_edges'],128)
        self.assertEqual(report['audit']['nonmanifold_edges'],0)
        inner,inner_rejections=offset_wall_rings(rings,width_mm=.24,side='inner')
        self.assertEqual(len(inner),4)
        for width in (.3,.4):
            with self.subTest(width=width):
                _,fails=offset_wall_rings(rings,width_mm=width,side='outer')
                self.assertGreater(len(fails),0)
                with self.assertRaises(ValueError):
                    wall_surface(rings,width_mm=width,side='outer')


if __name__ == '__main__':unittest.main(verbosity=2)
