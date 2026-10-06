#!/usr/bin/env python3
"""R81 golden test: byte-level regression net for make_range + process.

The R81 streaming refactor (R2-2026-09-07.65) rewrote both postproc paths from
'load the whole file as one Python list' (the Pi Zero RAM killer of field log
.63: 32MB source -> ~150MB of string objects -> swap storm -> 'Timer too
close' during range generation) to two-pass streaming. The refactor was
verified byte-identical against the PREVIOUS builder (.64) - this script
keeps that guarantee alive: it rebuilds the 23 fixture cases, runs them
through the CURRENT module and compares MD5s + change summaries against the
frozen references.

RE-FREEZE HISTORY: the references were originally frozen from the .64 code
(R81). R87.2 re-froze them from the R87.2 builder: make_range now re-derives
APPLY_TYPE markers from ;TYPE: comments when the source carries none (field
log .71 - the whole model printed as 'solid infill'), which is a deliberate
output change for such sources. The .64 reference is preserved in the .64
release ZIP. If this test fails after an edit to make_range/process, the
output of the edited code is no longer byte-identical to the frozen
reference - either fix the edit or (deliberate change only!) re-freeze with
--freeze=<old_module.py>.

Usage:
    python3 tools/r81_golden_check.py [--freeze=path/to/old_r2_postproc.py]
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# frozen from the .64 builder (R81), re-frozen from R87.2 - 23 cases
REF_MD5 = {
 'mr01': 'ecfecfbb517eecb71e0a1c778b07fd08',
 'mr02': '0b3af2fc484df120f9f4dc3fc4347eb8',
 'mr03': 'bc551cd152b3b652ace80d4322a5ef75',
 'mr04': 'c7a71fe81ab3e75a93b35f089714ab1e',
 'mr05': '6835665498237cc9339959d407c0d482',
 'mr06': '17ad9197732255092d32ff8b92e0f021',
 'mr07': 'e981a6109b3fbed5740e138c97ae1425',
 'mr08': 'ab395b58ff04132fd4bb44790e307adc',
 'mr09': 'b510f025bc9f11b3a756e5b5124f0d1a',
 'mr10': 'd042cd14bd30b3f5d3c1a9dddceb76f8',
 'mr11': '8bfae9b77a21c161220550f8c4ae1b24',
 'mr12': '04796069418f6ab5fea9c806f641b69a',
 'mr13': '6418854b598c2a4631402cba66cd0a72',
 'pr01': '79e28c82893f77486883839b30499edb',
 'pr02': 'c5ca9a4bc68a3f96c5ec661b862af0b6',
 'pr03': '0d14ef2caebcd00e7d5af20d9f710a79',
 'pr04': '0f8936af469f0f7fc4643fe053df0505',
 'pr05': '79e28c82893f77486883839b30499edb',
 'pr06': 'b5824d90a2dc7022df18bee5303afd81',
 'pr07': '17fdc789395c2d6f83efc279bb751f21',
 'pr08': '0d14ef2caebcd00e7d5af20d9f710a79',
 'pr09': 'd38293831fb7ef6f1d31c7056ec2745e',
 'pr10': 'c4caae4ffb28c45721fd09dbe50a066d',
 }

REF_SUMMARY = {
 'mr01': {'nl': 8, 'size': 3994},
 'mr02': {'nl': 10, 'size': 10317},
 'mr03': {'nl': 10, 'size': 10161},
 'mr04': {'nl': 9, 'size': 10387},
 'mr05': {'nl': 10, 'size': 16582},
 'mr06': {'nl': 10, 'size': 13924},
 'mr07': {'nl': 7, 'size': 3626},
 'mr08': {'nl': 6, 'size': 3280},
 'mr09': {'nl': 8, 'size': 7098},
 'mr10': {'nl': 8, 'size': 10189},
 'mr11': {'nl': 8, 'size': 6739},
 'mr12': {'nl': 2, 'size': 1798},
 'mr13': {'nl': 30, 'size': 18083},
 'pr01': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 9, 'marks_added': 9, 'method': 'layer comments', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 18, 'upgraded': False, 'upgraded_from': 'v1', 'volumetric': False},
 'pr02': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 9, 'marks_added': 9, 'method': 'layer comments', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 18, 'upgraded': False, 'upgraded_from': 'v1', 'volumetric': False},
 'pr03': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 8, 'marks_added': 8, 'method': 'Z scan', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 0, 'upgraded': False, 'upgraded_from': 'v1', 'volumetric': False},
 'pr04': {'by_object': False, 'info_added': False, 'layers': 0, 'marks_added': 0, 'method': None, 'retract_pairs': 0, 'skipped': True, 'tagged': False, 'types': 0, 'upgraded': False, 'upgraded_from': 'v1'},
 'pr05': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 9, 'marks_added': 9, 'method': 'layer comments', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 18, 'upgraded': True, 'upgraded_from': 'v1', 'volumetric': False},
 'pr06': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 9, 'marks_added': 9, 'method': 'layer comments', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 18, 'upgraded': False, 'upgraded_from': 'v1', 'volumetric': False},
 'pr07': {'by_object': False, 'info_added': False, 'layers': 0, 'marks_added': 0, 'method': None, 'retract_pairs': 0, 'skipped': True, 'tagged': False, 'types': 0, 'upgraded': False, 'upgraded_from': 'v1'},
 'pr08': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 8, 'marks_added': 8, 'method': 'Z scan', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 0, 'upgraded': False, 'upgraded_from': 'v1', 'volumetric': False},
 'pr09': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 9, 'marks_added': 9, 'method': 'layer comments', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 18, 'upgraded': False, 'upgraded_from': 'v1', 'volumetric': False},
 'pr10': {'by_object': False, 'fw': '', 'info_added': True, 'layers': 9, 'marks_added': 9, 'method': 'layer comments', 'retract_pairs': 0, 'skipped': False, 'slicer': '', 'tagged': True, 'types': 18, 'upgraded': False, 'upgraded_from': 'v1', 'volumetric': False},
 }

CASES = [
    ('mr01', dict(src='vase_m83.gcode', start=5, end=12)),
    ('mr02', dict(src='vase_m83.gcode', start=5, end=12, floor=2, brim=1)),
    ('mr03', dict(src='vase_m83.gcode', start=5, end=12, floor=2, floor_shape='outline', floor_fill='grid')),
    ('mr04', dict(src='vase_m83.gcode', start=5, end=12, floor=1, floor_shape='outline', floor_fill='solid')),
    ('mr05', dict(src='vase_m83.gcode', start=5, end=12, top=2, top_shape='hull', top_fill='solid')),
    ('mr06', dict(src='vase_m83.gcode', start=5, end=12, floor=1, top=1, brim=2, floor_shape='outline', top_shape='outline')),
    ('mr07', dict(src='vase_m83.gcode', start=1, end=8)),                      # start clamps to 2
    ('mr08', dict(src='vase_m83.gcode', start=25, end=999)),                   # end clamps to total
    ('mr09', dict(src='vase_m82_exc.gcode', start=3, end=9, floor=1, brim=1)),
    ('mr10', dict(src='vase_m82_g92.gcode', start=3, end=9, top=1)),
    ('mr11', dict(src='vase_nonl.gcode', start=4, end=10, floor=1)),           # no trailing newline
    ('mr12', dict(src='vase_m83.gcode', start=2, end=3)),                      # minimal range
    ('mr13', dict(src='vase_m83.gcode', start=2, end=30, top=1, top_shape='outline', top_fill='solid')),
]
PCASES = [
    ('pr01', 'orca_nl.gcode'),
    ('pr02', 'cura.gcode'),
    ('pr03', 'zscan.gcode'),           # no layer comments, no ;TYPE:
    ('pr04', 'tagged.gcode'),          # skip (already tagged)
    ('pr05', 'v1.gcode'),              # v1 -> v4 upgrade
    ('pr06', 'orca_nonl.gcode'),       # no trailing newline
    ('pr07', 'plot.gcode'),            # R2-PLOT skip
    ('pr08', 'zscan_cura_like.gcode'), # Z-scan with extruding Z moves
    ('pr09', 'orca_finfo.gcode'),      # _FILE_INFO in head, NO old tag (index-world offset)
    ('pr10', 'cura_finfo.gcode'),      # Cura layers + _FILE_INFO head
]


def vase(path, layers=30, e_rel=True, trailing_nl=True, exclude=False, g92_reset=False):
    L = ['; CONFIG_BLOCK', '; layer_height = 0.2', '; line_width = 0.6',
         '; filament_type = PLA', '; nozzle_diameter = 0.6',
         'M104 S215', 'M140 S60', 'M190 S60', 'M109 S215',
         'G21', 'G90', 'M83' if e_rel else 'M82', 'G92 E0']
    if exclude:
        L += ['EXCLUDE_OBJECT_DEFINE NAME=VASE_1 CENTER=110,110 POLYGON=[[80,80],[140,80],[140,140],[80,140]]']
    L += ['; R2-POSTPROC v4', '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.2 LINE_WIDTH=0.6 TOTAL_LAYERS=%d BY_OBJECT=0' % layers]
    L += ['PRINT_START MATERIAL=PLA BED=60 HOTEND_FIRST=215 HOTEND_AFTER=210 LAYER_HEIGHT=0.2 TOTAL_LAYERS=%d' % layers]
    L += ['EXCLUDE_OBJECT_START NAME=VASE_1']
    e = 0.0
    for lay in range(1, layers + 1):
        L.append('LAYER_MARK')
        L.append(';LAYER_CHANGE')
        L.append(';Z:%.3f' % (0.2 * lay))
        L.append(';TYPE:Outer wall')
        L.append('G0 X30 Y30 Z%.3f F6000' % (0.2 * lay))
        if g92_reset and not e_rel:
            L.append('G92 E%.3f' % (lay * 10))
        for (cx, cy) in ((70, 30), (70, 70), (30, 70), (30, 30)):
            if e_rel:
                e = 2.0
                L.append('G1 X%d Y%d E%.3f F1800' % (cx, cy, e))
            else:
                e += 2.0
                L.append('G1 X%d Y%d E%.3f F1800' % (cx, cy, e))
        L.append(';TYPE:Top surface')
        L.append('G1 X50 Y50 E%.3f F1200' % (1.0 if e_rel else e + 1.0))
        if lay == 1:
            L.append('M106 S200')
    L.append('EXCLUDE_OBJECT_END NAME=VASE_1')
    L.append('M107')
    L.append('PRINT_END')
    txt = '\n'.join(L) + ('\n' if trailing_nl else '')
    open(path, 'w').write(txt)


def orca(path, trailing_nl=True, tagged=False, v1=False, no_layers=False, cura=False):
    L = ['; CONFIG_BLOCK', '; layer_height = 0.16', '; line_width = 0.68',
         '; filament_type = PLA', '; nozzle_diameter = 0.6', '; outer_wall_speed = 60',
         '; outer_wall_acceleration = 500', '; wall_loops = 1',
         'M104 S225', 'M140 S55', 'M109 S225', 'G21', 'G90', 'M83', 'G92 E0']
    if tagged:
        L = ['; R2-POSTPROC v4'] + L
    if v1:
        L = ['; R2-POSTPROC v1', '_FILE_INFO MATERIAL=PLA TOTAL_LAYERS=9'] + L
    if not no_layers:
        L.append('G28')
    e = 0.0
    for lay in range(1, 10):
        if cura:
            L.append(';LAYER:%d' % lay)
        elif not no_layers:
            L.append(';LAYER_CHANGE')
        if not no_layers:
            L.append(';Z:%.3f' % (0.16 * lay))
            L.append(';TYPE:Outer wall')
            L.append('G0 X40 Y40 Z%.3f F9000' % (0.16 * lay))
            L.append('G1 X80 Y40 E1.2 F3600')
            L.append('G1 X80 Y80 E1.2 F3600')
            L.append(';TYPE:Ironing')
            L.append('G1 X60 Y60 E0.2 F2700')
            L.append('M204 S500')
        else:
            # real Z-scan material: extruding moves that CARRY Z (Cura style)
            L.append('G1 X40 Y40 Z%.3f E0.6 F3600' % (0.16 * lay))
            L.append('G1 X80 Y40 E1.2 F3600')
            L.append('G1 X80 Y80 E1.2 F3600')
    L.append('M107')
    L.append('; end of gcode')
    open(path, 'w').write('\n'.join(L) + ('\n' if trailing_nl else ''))


def orca_finfo(path, **kw):
    """orca fixture with a non-comment _FILE_INFO line in the head (no old tag):
    shifts the raw vs. upgrade-filtered index worlds - the apply positions
    must still land byte-exact."""
    orca(path, **kw)
    txt = open(path).read()
    L = txt.split('\n')
    L.insert(6, '_FILE_INFO MATERIAL=PLA LAYER_HEIGHT=0.16 LINE_WIDTH=0.68 TOTAL_LAYERS=9 BY_OBJECT=0')
    open(path, 'w').write('\n'.join(L))


def build_fixtures(d):
    vase(os.path.join(d, 'vase_m83.gcode'))
    vase(os.path.join(d, 'vase_m82_exc.gcode'), e_rel=False, exclude=True)
    vase(os.path.join(d, 'vase_m82_g92.gcode'), e_rel=False, g92_reset=True)
    vase(os.path.join(d, 'vase_nonl.gcode'), trailing_nl=False)
    orca(os.path.join(d, 'orca_nl.gcode'))
    orca(os.path.join(d, 'cura.gcode'), cura=True)
    orca(os.path.join(d, 'zscan.gcode'), no_layers=True)
    orca(os.path.join(d, 'tagged.gcode'), tagged=True)
    orca(os.path.join(d, 'v1.gcode'), v1=True)
    orca(os.path.join(d, 'orca_nonl.gcode'), trailing_nl=False)
    open(os.path.join(d, 'plot.gcode'), 'w').write('; R2-PLOT v1 pen plot\nG28\nG0 X10 Y10\n')
    orca(os.path.join(d, 'zscan_cura_like.gcode'), no_layers=True)
    orca_finfo(os.path.join(d, 'orca_finfo.gcode'))
    orca_finfo(os.path.join(d, 'cura_finfo.gcode'), cura=True)


def run_battery(mod, d):
    """returns {case: (md5, summary-without-file)}"""
    out = {}
    for name, kw in CASES:
        kw = dict(kw)
        src = os.path.join(d, kw.pop('src'))
        rng, nl = mod.make_range(src, **kw)
        out[name] = (hashlib.md5(open(rng, 'rb').read()).hexdigest(),
                     {'nl': nl, 'size': os.path.getsize(rng)})
    for name, fn in PCASES:
        p = os.path.join(d, fn)
        summ = mod.process(p)
        out[name] = (hashlib.md5(open(p, 'rb').read()).hexdigest(),
                     {k: v for k, v in summ.items() if k != 'file'})
    return out


def main():
    freeze = None
    for a in sys.argv[1:]:
        if a.startswith('--freeze='):
            freeze = a.split('=', 1)[1]
    if freeze:
        spec = importlib.util.spec_from_file_location('r2p_old', freeze)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        d = tempfile.mkdtemp(prefix='g81freeze_')
        build_fixtures(d)
        res = run_battery(old, d)
        ref = {'md5': {k: v[0] for k, v in res.items()},
               'summaries': {k: v[1] for k, v in res.items()}}
        print(json.dumps(ref, indent=1, sort_keys=True))
        print('# re-freeze: paste the block above into REF_MD5 / REF_SUMMARY', file=sys.stderr)
        return 0

    spec = importlib.util.spec_from_file_location('r2p', os.path.join(HERE, 'r2_postproc.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    d = tempfile.mkdtemp(prefix='g81run_')
    build_fixtures(d)
    res = run_battery(mod, d)
    fails = 0
    for name in sorted(res):
        md5, summ = res[name]
        if name not in REF_MD5:
            print('FAIL %s: no reference (re-freeze needed)' % name)
            fails += 1
            continue
        if md5 != REF_MD5[name]:
            print('FAIL %s: output differs from the frozen reference (md5 %s != %s)'
                  % (name, md5[:10], REF_MD5[name][:10]))
            fails += 1
        # R84: newer builders add summary keys (retract_pairs, slicer, ...) -
        # compare only the keys the reference knows (byte-identical output
        # is the real contract; the reference must stay re-baseline-free)
        _ref_summ = REF_SUMMARY.get(name)
        _summ_cmp = {k: v for k, v in summ.items() if k in _ref_summ} if _ref_summ else summ
        if _summ_cmp != _ref_summ:
            print('FAIL %s: summary differs: %r != %r' % (name, _summ_cmp, _ref_summ))
            fails += 1
    if not fails:
        print('R81 golden check: %d/%d cases byte-identical to the R87.2 reference' % (len(res), len(res)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
