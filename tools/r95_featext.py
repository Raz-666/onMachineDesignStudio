#!/usr/bin/env python3
"""R95: extend the feature system from 12 to 16 codes (field log .73).

New DETECTABLE slicer features (all slicer families mapped in TYPE_MAP):
  OVERHANG-PERIM   Prusa/Orca 'Overhang perimeter'  (slow overhang wall parts)
  INTERNAL-BRIDGE  Prusa/Orca 'Internal bridge'
  PRIME-TOWER      Orca 'Prime tower' / Prusa 'Wipe tower' / Cura 'PRIME-TOWER'
  CUSTOM           'Custom' (custom G-code sections - the mystery feature with
                   the low accel values seen on the LCD)

NOT a separate g-code type (research): 'small perimeters' = a SPEED setting
inside wall features (Orca default 50%) - no ;TYPE: marker exists. It shows
in the file info instead (SPEED_SMALL/ACCEL_SMALL from the config header).

One-shot generator - extends the literal code lists, the _STATE variables,
the _FILE_INFO replay mapping, the reset lists and both LCD feature menus.
"""
import re

NEW = [
    # sid, code, canon, pfx, lcd name
    ('oh', 'overhangperim', 'OVERHANG-PERIM', 'OH', 'Overhang Wall'),
    ('ib', 'internalbridge', 'INTERNAL-BRIDGE', 'IB', 'Internal Bridge'),
    ('pt', 'primetower', 'PRIME-TOWER', 'PT', 'Prime Tower'),
    ('cu', 'custom', 'CUSTOM', 'CU', 'Custom Code'),
]
OLD_LIST = "['wallouter','wallinner','infillsparse','infillsolid','surfacetop','surfacebottom','bridge','gaps','support','ironing','skirt','brim']"
NEW_LIST = OLD_LIST[:-1] + ",'overhangperim','internalbridge','primetower','custom']"

def sub(path, old, new, n=None, tag=''):
    s = open(path, encoding='utf-8').read()
    c = s.count(old)
    assert c > 0 and (n is None or c == n), '%s %s: count=%d' % (path, tag, c)
    s = s.replace(old, new)
    open(path, 'w', encoding='utf-8').write(s)
    print('  %-38s %2d x %s' % (path, c, tag))

# ---- A) literal code lists in the macros ----
print('[A] code lists 12 -> 16:')
for f in ['macros/04_notify.cfg', 'macros/05_materials.cfg',
          'macros/06_temp_controls.cfg', 'macros/07_start_confirm.cfg',
          'macros/08_print_start_stop.cfg', 'macros/10_live_tuning.cfg']:
    sub(f, OLD_LIST, NEW_LIST, tag='codes')

# ---- B) 05_materials preset dict ----
print('[B] material preset dict:')
sub('macros/05_materials.cfg',
    "'brim': [sv.ovf_brim_on|default(False), sv.ovf_brim_spd|default(100)|float, sv.ovf_brim_acc|default(0)|float, sv.ovf_brim_flw|default(100)|float],",
    "'brim': [sv.ovf_brim_on|default(False), sv.ovf_brim_spd|default(100)|float, sv.ovf_brim_acc|default(0)|float, sv.ovf_brim_flw|default(100)|float],\n"
    + '\n'.join(
        "        '%s': [sv.ovf_%s_on|default(False), sv.ovf_%s_spd|default(100)|float, sv.ovf_%s_acc|default(0)|float, sv.ovf_%s_flw|default(100)|float],"
        % (c, c, c, c, c) for _, c, _, _, _ in NEW),
    1, 'preset dict')

# ---- C) 04_notify NONE chain ----
print('[C] notify NONE chain:')
sub('macros/04_notify.cfg',
    "or sv.ovf_brim_on|default(False)) %}NONE",
    "or sv.ovf_brim_on|default(False)"
    + ''.join(" or sv.ovf_%s_on|default(False)" % c for _, c, _, _, _ in NEW)
    + ") %}NONE", 1, 'NONE chain')

# ---- D) 01_state variables ----
print('[D] _STATE file_feat variables:')
sub('macros/01_state.cfg', "variable_file_feat_spd_brim: 0.0",
    "variable_file_feat_spd_brim: 0.0\n"
    + '\n'.join("variable_file_feat_spd_%s: 0.0" % c for _, c, _, _, _ in NEW), 1, 'spd vars')
sub('macros/01_state.cfg', "variable_file_feat_acc_brim: 0.0",
    "variable_file_feat_acc_brim: 0.0\n"
    + '\n'.join("variable_file_feat_acc_%s: 0.0" % c for _, c, _, _, _ in NEW), 1, 'acc vars')

# ---- E) 08: _FILE_INFO mapping + reset lists ----
print('[E] _FILE_INFO replay + resets:')
sub('macros/08_print_start_stop.cfg',
    "('FS_BRIM','file_feat_spd_brim'),",
    "('FS_BRIM','file_feat_spd_brim'),\n"
    + ' '.join("('FS_%s','file_feat_spd_%s')," % (n.replace('-', '_'), c)
               for _, c, n, _, _ in NEW), 1, 'FS map')
sub('macros/08_print_start_stop.cfg',
    "('FA_BRIM','file_feat_acc_brim'),",
    "('FA_BRIM','file_feat_acc_brim'),\n"
    + ' '.join("('FA_%s','file_feat_acc_%s')," % (n.replace('-', '_'), c)
               for _, c, n, _, _ in NEW), 1, 'FA map')
sub('macros/08_print_start_stop.cfg',
    "'file_feat_spd_ironing','file_feat_spd_skirt','file_feat_spd_brim',",
    "'file_feat_spd_ironing','file_feat_spd_skirt','file_feat_spd_brim',\n"
    + ' '.join("'file_feat_spd_%s'," % c for _, c, _, _, _ in NEW), 1, 'spd reset')
sub('macros/08_print_start_stop.cfg',
    "'file_feat_acc_ironing','file_feat_acc_skirt','file_feat_acc_brim',",
    "'file_feat_acc_ironing','file_feat_acc_skirt','file_feat_acc_brim',\n"
    + ' '.join("'file_feat_acc_%s'," % c for _, c, _, _, _ in NEW), 1, 'acc reset')

# ---- F) LCD: 4 submenus in Pre-Print > Features + Live > Features ----
print('[F] LCD feature menus:')
P = 'menus/lcd_menues.cfg'
t = open(P, encoding='utf-8').read()

def block(header):
    i = t.index('[menu %s]' % header)
    j = t.index('\n[menu ', i + 1)
    return t[i:j + 1]

def clone(template, sid, code, canon, name, pfx):
    b = template
    b = b.replace('WALL-OUTER', canon)
    b = b.replace('WALLOUTER', code.upper())
    b = b.replace('wallouter', code)
    b = b.replace('Outer Wall', name)
    b = b.replace('__ow', '__' + sid)
    b = b.replace('OW:', pfx + ':')
    b = b.replace('outer wall', name.lower())
    return b

pre_tpl = block('__main __preprint __feat __ow')
live_tpl = block('__main __live __feat __ow')
pre_act = block('__main __preprint __file __acwall')
live_act = block('__main __live __file __acwall')

# insert AFTER the last (brim) block of each group
def insert_after(anchor_header, payload):
    global t
    b = block(anchor_header)
    t = t.replace(b, b + payload, 1)

add_pre = ''.join(clone(pre_tpl, *f) for f in NEW)
add_live = ''.join(clone(live_tpl, *f) for f in NEW)
add_pact = ''.join(clone(pre_act, *f) for f in NEW)
add_lact = ''.join(clone(live_act, *f) for f in NEW)
insert_after('__main __preprint __feat __bm', add_pre)
insert_after('__main __live __feat __bm', add_live)
insert_after('__main __preprint __file __acbrim', add_pact)
insert_after('__main __live __file __acbrim', add_lact)
open(P, 'w', encoding='utf-8').write(t)
print('  menus/lcd_menues.cfg           +4 preprint +4 live submenus, +8 activators')

# ---- G) r2_postproc: TYPE_MAP + CFG_KEYS ----
print('[G] TYPE_MAP + CFG_KEYS:')
R = 'tools/r2_postproc.py'
s = open(R, encoding='utf-8').read()
anchor = "    'support material': 'SUPPORT',\n    'support material interface': 'SUPPORT',\n}"
assert s.count(anchor) == 1
s = s.replace(anchor,
    "    'support material': 'SUPPORT',\n    'support material interface': 'SUPPORT',\n"
    "    # R95 (field log .73): the remaining slicer features, all families.\n"
    "    # Prusa/Orca slow-overhang walls, internal bridges, the purge tower\n"
    "    # (3 spellings) - now EDITABLE features; approximations documented.\n"
    "    'overhang perimeter': 'OVERHANG-PERIM',\n"
    "    'internal bridge': 'INTERNAL-BRIDGE',\n"
    "    'wipe tower': 'PRIME-TOWER',\n"
    "    'prime tower': 'PRIME-TOWER',\n"
    "    'prime-tower': 'PRIME-TOWER',\n"
    "    'thin wall': 'WALL-INNER',        # SuperSlicer: no own override\n"
    "    'support transition': 'SUPPORT',\n"
    "    'ooze shield': 'SKIRT',\n"
    "    # Cura: dashed forms + combined skin (top/bottom share one type)\n"
    "    'skin': 'SURFACE-TOP',\n"
    "    'top-skin': 'SURFACE-TOP',\n"
    "    'bottom-skin': 'SURFACE-BOTTOM',\n"
    "    'support-interface': 'SUPPORT',\n"
    "    'raft': 'SURFACE-BOTTOM',\n"
    "    'infill': 'INFILL-SPARSE',\n}")
anchor = "    'ironing_flow': 'IRONING_FLOW',\n    'ironing_spacing': 'IRONING_SPACING',\n}"
assert s.count(anchor) == 1
s = s.replace(anchor,
    "    'ironing_flow': 'IRONING_FLOW',\n    'ironing_spacing': 'IRONING_SPACING',\n"
    "    # R95: small perimeters are a SPEED setting inside the walls (no\n"
    "    # separate ;TYPE: exists) - shown in the file info instead\n"
    "    'small_perimeter_speed': 'SPEED_SMALL',\n"
    "    'small_perimeter_acceleration': 'ACCEL_SMALL',\n}")
open(R, 'w', encoding='utf-8').write(s)
print('  tools/r2_postproc.py            TYPE_MAP +13, CFG_KEYS +2')
print('[ok] R95 extension done')
