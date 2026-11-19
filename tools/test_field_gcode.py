"""Field-ingestion hard test: three foreign, older, non-vase G-code files.

MAN_V3 (Slice Beam 0.3.0; PrusaSlicer-family ;TYPE: tags; supports, brim,
ironing, custom prime lines), Pumpkin_Scream_MULTI-011 (Kiri:Moto 4.3.2;
NO G90 anywhere; `; feature <name>` dialect; nonplanar ramped top) and
vwbus (Kiri:Moto 4.3.1; ~79 percent of all paths are support). These
files exercise ingestion, documented dialect assumptions and feature
tagging on real slicer output the pipeline never saw. Never export-ready.
"""
import gzip
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from collections import Counter
from path_evidence import PathEvidence
from r2_shadow import Shadow

FIXTURES=Path(__file__).resolve().parents[1]/'testfixtures'

FIELD_FILES={
    'MAN_V3': dict(sha256='cc0aaba2b53a64ca9c5130706e7047e5222f4b8f9ba91e59aeab72bfbf96e3a6',
                   options=dict(klipper_passive=True,assume_klipper_defaults=True)),
    'Pumpkin_Scream_MULTI-011': dict(sha256='b33ce2777679151137a206ad3e063411fda37d548fafeaff5a3e3c6e94c3822e',
                                     options=dict(klipper_passive=True,assume_klipper_defaults=True,
                                                  assumed_passive=('G80',))),
    'vwbus': dict(sha256='c7e7a18a6abed88567144f6b8eab0d02491efe94f86b5b013107efcf7f025cdd',
                  options=dict(klipper_passive=True,assume_klipper_defaults=True,
                               assumed_passive=('G80',))),
}


def unpack(name):
    directory=tempfile.mkdtemp(prefix='r2-field-')
    path=Path(directory)/(name+'.gcode')
    with gzip.open(FIXTURES/(name+'.gcode.gz'),'rb') as source,path.open('wb') as target:
        shutil.copyfileobj(source,target)
    return path


def ingest(path,options):
    """Full passive parse; returns (kind counts, evidence report, z levels)."""
    state=Shadow(**options)
    evidence=PathEvidence()
    kinds=Counter()
    z_levels=set()
    with path.open('r',encoding='utf-8',errors='surrogateescape',newline='') as source:
        number=0
        while True:
            raw=source.readline(1024*1024+1)
            if not raw:
                break
            number+=1
            record=state.process(raw,number)
            kinds[record['kind']]+=1
            evidence.consume(record)
            if record['kind']=='move':
                delta=record['commanded_e_delta_mm']
                z=record['end_mm']['Z']
                if delta and delta>0 and z is not None:
                    z_levels.add(round(z,4))
    return kinds,evidence.report(),z_levels


class FieldFixtureTests(unittest.TestCase):
    def test_fixture_hashes_guard(self):
        for name,spec in FIELD_FILES.items():
            with self.subTest(name=name):
                digest=hashlib.sha256((FIXTURES/(name+'.gcode.gz')).read_bytes()).hexdigest()
                self.assertEqual(digest,spec['sha256'])

    def test_read_only(self):
        for name in FIELD_FILES:
            with self.subTest(name=name):
                fixture=FIXTURES/(name+'.gcode.gz')
                before=hashlib.sha256(fixture.read_bytes()).digest()
                path=unpack(name)
                try:
                    ingest(path,FIELD_FILES[name]['options'])
                finally:
                    shutil.rmtree(path.parent)
                self.assertEqual(hashlib.sha256(fixture.read_bytes()).digest(),before)


class ManV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=unpack('MAN_V3')
        cls.kinds,cls.report,cls.z_levels=ingest(cls.path,FIELD_FILES['MAN_V3']['options'])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.path.parent)

    def test_full_ingestion_no_unknowns(self):
        self.assertEqual(dict(self.kinds),
                         dict(comment=44055,non_motion_event=449,mode=5,home=1,
                              move=358379,coordinate_reset=325,motors_off=1))
        self.assertNotIn('unknown',self.kinds)

    def test_layer_geometry(self):
        self.assertEqual(len(self.z_levels),324)
        self.assertAlmostEqual(min(self.z_levels),0.24,places=3)
        self.assertAlmostEqual(max(self.z_levels),51.76,places=3)
        counts=self.report['counts']
        self.assertEqual(counts['paths'],9190)
        self.assertEqual(counts['segments'],228780)
        self.assertEqual(counts.get('nonplanar_paths',0),0)

    def test_feature_roles_split_helpers_from_model(self):
        roles=self.report['paths_by_role']
        self.assertEqual(roles['helper_hint_excluded'],5333)
        self.assertEqual(roles['outer_wall_hint_unverified'],1954)
        self.assertEqual(roles['unclassified'],1903)
        features=self.report['paths_by_feature_hint']
        self.assertEqual(features['Support material'],4983)
        self.assertEqual(features['Support material interface'],25)
        self.assertEqual(features['Skirt/Brim'],144)
        self.assertEqual(features['Ironing'],179)
        self.assertEqual(features['Custom'],2)
        self.assertEqual(features['External perimeter'],1954)
        self.assertEqual(features['Perimeter'],1493)
        self.assertEqual(features['Overhang perimeter'],143)
        self.assertEqual(features['Solid infill'],226)
        self.assertEqual(features['Top solid infill'],13)
        self.assertEqual(features['Internal infill'],18)
        self.assertEqual(features['Bridge infill'],10)

    def test_conservative_mode_documents_start_block_gap(self):
        # Without assumptions the first start block is unparseable: it sets
        # G90/M83 but never G21, so units stay unknown until the second
        # block. The 9 unknown records are all confined to that prime block.
        kinds,report,_=ingest(self.path,dict(klipper_passive=True))
        self.assertEqual(kinds['unknown'],9)
        self.assertEqual(kinds['home'],1)
        self.assertEqual(report['counts']['paths'],9188)
        self.assertEqual(report['paths_by_role']['helper_hint_excluded'],5331)


class KiriMotoTests(unittest.TestCase):
    def test_pumpkin_ingestion_and_features(self):
        path=unpack('Pumpkin_Scream_MULTI-011')
        try:
            kinds,report,z_levels=ingest(path,FIELD_FILES['Pumpkin_Scream_MULTI-011']['options'])
        finally:
            shutil.rmtree(path.parent)
        self.assertEqual(dict(kinds),
                         dict(comment=2369,non_motion_event=221,home=1,assumed_passive=1,
                              mode=2,move=425227,klipper_passive=253,motors_off=1))
        self.assertNotIn('unknown',kinds)
        # 4.3.2 never issues G90; ingestion needs the recorded opt-in default.
        # Kiri:Moto ramps Z on the top surfaces: 192 nonplanar paths, 3252
        # distinct extruding Z values across 251 nominal layers.
        self.assertEqual(report['counts']['nonplanar_paths'],192)
        self.assertEqual(report['counts']['paths'],7079)
        self.assertEqual(len(z_levels),3252)
        self.assertAlmostEqual(min(z_levels),0.2,places=3)
        self.assertAlmostEqual(max(z_levels),50.2,places=3)
        roles=report['paths_by_role']
        self.assertEqual(roles['helper_hint_excluded'],415)
        self.assertEqual(roles['unclassified'],6664)
        features=report['paths_by_feature_hint']
        self.assertEqual(features['support'],400)
        self.assertEqual(features['brim'],15)
        self.assertEqual(features['shells'],2482)
        self.assertEqual(features['solid fill'],302)
        self.assertEqual(features['sparse infill'],3879)
        self.assertEqual(features['UNMARKED'],1)

    def test_vwbus_ingestion_support_dominated(self):
        path=unpack('vwbus')
        try:
            kinds,report,z_levels=ingest(path,FIELD_FILES['vwbus']['options'])
        finally:
            shutil.rmtree(path.parent)
        self.assertEqual(dict(kinds),
                         dict(comment=11384,non_motion_event=110,home=1,assumed_passive=1,
                              mode=2,move=468863,klipper_passive=419,motors_off=1))
        self.assertNotIn('unknown',kinds)
        self.assertEqual(report['counts']['paths'],39243)
        self.assertEqual(report['counts'].get('nonplanar_paths',0),0)
        self.assertEqual(len(z_levels),418)
        self.assertAlmostEqual(min(z_levels),0.2,places=3)
        self.assertAlmostEqual(max(z_levels),83.4,places=3)
        roles=report['paths_by_role']
        # ~79 percent of all paths are support: helpers must stay separable.
        self.assertEqual(roles['helper_hint_excluded'],31144)
        self.assertEqual(roles['unclassified'],8099)
        features=report['paths_by_feature_hint']
        self.assertEqual(features['support'],31144)
        self.assertEqual(features['shells'],4213)
        self.assertEqual(features['sparse infill'],3474)
        self.assertEqual(features['solid fill'],411)
        self.assertEqual(features['UNMARKED'],1)
        self.assertGreater(roles['helper_hint_excluded'],
                           4*sum(v for k,v in features.items()
                                 if k in ('shells','solid fill','sparse infill'))//10)


if __name__ == '__main__':unittest.main(verbosity=2)
