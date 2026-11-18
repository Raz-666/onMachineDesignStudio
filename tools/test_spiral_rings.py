"""Synthetic helix oracles for per-revolution ring sampling of spiral walls."""
import math
import unittest
from spiral_rings import spiral_rings

SEGMENTS_PER_REVOLUTION=48


def helix(radius, revolutions, height_per_revolution, *, radius_fn=None):
    points=[]
    count=int(revolutions*SEGMENTS_PER_REVOLUTION)+1
    for i in range(count):
        angle=2*math.pi*i/SEGMENTS_PER_REVOLUTION
        r=radius if radius_fn is None else radius_fn(i)
        points.append((r*math.cos(angle),r*math.sin(angle),
                       height_per_revolution*i/SEGMENTS_PER_REVOLUTION))
    return points


class SpiralRingTests(unittest.TestCase):
    def test_helix_ring_count_bands_and_radii(self):
        # 1/16 and 1/1536 are binary-exact, keeping sample placement deterministic.
        points=helix(10,12,1/16)
        result=spiral_rings(points,pitch_mm=1/16,samples_per_revolution=32)
        self.assertEqual(result['ring_count'],12)
        self.assertEqual(result['dropped_incomplete_ring_samples'],0)
        self.assertTrue(all(ring['samples']==32 for ring in result['rings']))
        for r,ring in enumerate(result['rings']):
            lo,hi=ring['z_band_mm']
            self.assertGreaterEqual(lo,r/16-1e-12)
            self.assertLessEqual(hi,(r+1)/16+1e-12)
            xs=[p[0] for p in ring['points_mm']]
            ys=[p[1] for p in ring['points_mm']]
            self.assertLess(math.hypot(sum(xs)/32,sum(ys)/32),.05)
            for x,y in zip(xs,ys):
                radius=math.hypot(x,y)
                # Chord interpolation insets a sample by at most one segment
                # sagitta: R*(1-cos(pi/48)) ~ 0.0214 mm for R=10.
                self.assertLess(radius,10.0001)
                self.assertGreater(radius,9.97)
        self.assertEqual(result['direction'],'ascending')

    def test_incomplete_final_revolution_dropped(self):
        result=spiral_rings(helix(10,12.5,1/16),pitch_mm=1/16,samples_per_revolution=32)
        self.assertEqual(result['ring_count'],12)
        self.assertEqual(result['dropped_incomplete_ring_samples'],16)

    def test_descending_path(self):
        points=helix(4,6,1/16)[::-1]
        result=spiral_rings(points,pitch_mm=1/16,samples_per_revolution=8)
        self.assertEqual(result['direction'],'descending')
        self.assertEqual(result['ring_count'],6)
        self.assertTrue(all(ring['samples']==8 for ring in result['rings']))

    def test_parameter_and_path_validation(self):
        points=helix(10,3,1/16)
        for kwargs in (dict(pitch_mm=0,samples_per_revolution=8),
                       dict(pitch_mm=float('nan'),samples_per_revolution=8),
                       dict(pitch_mm=1/16,samples_per_revolution=2),
                       dict(pitch_mm=1/16,samples_per_revolution=257),
                       dict(pitch_mm=1/16,samples_per_revolution=8.0),
                       dict(pitch_mm=1,samples_per_revolution=8)):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                spiral_rings(points,**kwargs)
        for bad in ([(0,0,0),(1,0,.1)],
                    [(0,0,0),(1,0,.1),(0,0,.2),(0,0,.2)],
                    [(0,0,0),(1,0,float('nan')),(0,0,.2)],
                    [(0,0,0),(1,0,.1),(0,0,.2),[0,0,.3]],
                    [(0,0,0),(1,0,.1),(1,0,.05),(0,0,.2)]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                spiral_rings(bad,pitch_mm=1/32,samples_per_revolution=4)
        with self.assertRaises(ValueError):
            spiral_rings(helix(10,40,1/16),pitch_mm=1/16,samples_per_revolution=8)
        with self.assertRaises(ValueError):
            spiral_rings(helix(10,.9,1/16),pitch_mm=1/16,samples_per_revolution=8)

    def test_degenerate_rings_rejected(self):
        # XY collapses onto one line: rings are collinear, not simple polygons.
        line=[((i%2)*10,0,i/32) for i in range(97)]
        with self.assertRaises(ValueError):
            spiral_rings(line,pitch_mm=1/16,samples_per_revolution=4)

    def test_contract_labels(self):
        result=spiral_rings(helix(10,3,1/16),pitch_mm=1/16,samples_per_revolution=8)
        self.assertFalse(result['export_ready'])
        self.assertEqual(result['geometry'],'nozzle_centerline_per_revolution_rings')
        self.assertTrue(any('pitch' in limitation for limitation in result['limitations']))
        self.assertTrue(any('mix heights' in limitation for limitation in result['limitations']))


if __name__ == '__main__':unittest.main(verbosity=2)
