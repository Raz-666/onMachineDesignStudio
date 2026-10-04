#!/usr/bin/env python3
"""R60: rebuild feature menus (Pre-Print + new Live) + full File-Info mirror in Live."""
import re

P = 'menus/lcd_menues.cfg'
t = open(P).read()
t0 = t

FEATS = [
    ('ow', 'wallouter',     'WALL-OUTER',     'OW'),
    ('iw', 'wallinner',     'WALL-INNER',     'IW'),
    ('sp', 'infillsparse',  'INFILL-SPARSE',  'SP'),
    ('so', 'infillsolid',   'INFILL-SOLID',   'SO'),
    ('tp', 'surfacetop',    'SURFACE-TOP',    'TP'),
    ('bt', 'surfacebottom', 'SURFACE-BOTTOM', 'BT'),
    ('br', 'bridge',        'BRIDGE',         'BR'),
    ('gp', 'gaps',          'GAPS',           'GP'),
    ('su', 'support',       'SUPPORT',        'SU'),
    ('ir', 'ironing',       'IRONING',        'IR'),
    ('sk', 'skirt',         'SKIRT',          'SK'),
    ('bm', 'brim',          'BRIM',           'BM'),
]
BY_CODE = {c: (s, canon, pfx) for s, c, canon, pfx in FEATS}
AC_ID = {'ow': 'wall', 'iw': 'walli', 'sp': 'infi', 'so': 'solid', 'tp': 'surf', 'bt': 'surfb',
         'br': 'brid', 'gp': 'gaps', 'su': 'supp', 'ir': 'iron', 'sk': 'skir', 'bm': 'brim'}

ST = "printer['gcode_macro _STATE']"
SV = "printer['save_variables'].variables"

# ---- long names from the existing Pre-Print block ----
names = {}
for sid, code, canon, pfx in FEATS:
    m = re.search(r'\[menu __main __preprint __feat __' + sid + r'\]\ntype: list\nname: ([^\n]+)', t)
    assert m, 'missing name for ' + sid
    names[sid] = m.group(1)

def avail(canon, s='s'):
    return s + ".file_types|default('') == '' or '" + canon + "' in " + s + '.file_types'

def notin(canon, s=ST):
    return s + ".file_types|default('') != '' and '" + canon + "' not in " + s + '.file_types'

def fs_name(code):
    canon = BY_CODE[code][1]
    return ('(' + ST + '.file_feat_spd_' + code + "|default(0)|round|int|string ~ 'mm/s') if " + ST +
            '.file_feat_spd_' + code + "|default(0) > 0 else ('n/a' if " + notin(canon) + " else '--')")

def feat_submenu(parent, sid, code, canon, live):
    L = []
    L.append('[menu __main ' + parent + ' __feat __' + sid + ']')
    L.append('type: list')
    L.append('name: ' + names[sid])
    L.append('')
    # ---- On toggle (OFF resets to the file original via SET_OVERRIDE_VALUE) ----
    L.append('[menu __main ' + parent + ' __feat __' + sid + ' __on]')
    L.append('type: command')
    L.append('name: On: {' + SV + '.ovf_' + code + '_on|default(False)|string|upper}'
             "{' n/a' if " + notin(canon) + " else ''}")
    L.append('gcode:')
    L.append('    {% set s = ' + ST + ' %}')
    L.append('    {% if ' + avail(canon) + ' %}')
    L.append('        SET_OVERRIDE_VALUE NAME=feat_on_' + code + ' VALUE={1 if not ' +
             SV + '.ovf_' + code + '_on|default(False) else 0}')
    if live:
        L.append("        {% if s.current_type|default('') == '" + canon + "' %}")
        L.append('            APPLY_TYPE TYPE=' + canon)
        L.append('        {% endif %}')
    L.append('    {% else %}')
    L.append('        RESPOND MSG="' + canon + ' is not in this file - nothing to override"')
    L.append('    {% endif %}')
    L.append('')
    # ---- File original (measured) ----
    L.append('[menu __main ' + parent + ' __feat __' + sid + ' __fs]')
    L.append('type: command')
    L.append('name: File: {' + fs_name(code) + '}')
    L.append('gcode:')
    L.append('    {% set s = ' + ST + ' %}')
    L.append('    RESPOND MSG="[File] ' + canon + ' ORIGINAL: speed {s.file_feat_spd_' + code +
             '|default(0)|round|int} mm/s | accel {s.file_feat_acc_' + code +
             '|default(0)|round|int} mm/s2 | YOUR override: {printer[\'save_variables\'].variables.ovf_' + code +
             '_spd|default(100)|round|int}% x global {s.g_speed_clean|default(100)|round|int}% (speed), {printer[\'save_variables\'].variables.ovf_' + code +
             '_acc|default(0)|round|int} mm/s2 (accel) - OFF = back to the original"')
    L.append('')
    # ---- speed % ----
    L.append('[menu __main ' + parent + ' __feat __' + sid + ' __spd]')
    L.append('type: input')
    L.append("name: Spd: {'%3d' % menu.input} %")
    L.append('input: {' + SV + '.ovf_' + code + '_spd|default(100)}')
    L.append('input_min: 20')
    L.append('input_max: 200')
    L.append('input_step: 5')
    L.append('gcode:')
    L.append('    {% set s = ' + ST + ' %}')
    L.append('    {% if ' + avail(canon) + ' %}')
    L.append('        SET_OVERRIDE_VALUE NAME=feat_spd_' + code + ' VALUE={menu.input|round|int}')
    if live:
        L.append("        {% if s.current_type|default('') == '" + canon + "' %}")
        L.append('            APPLY_TYPE TYPE=' + canon)
        L.append('        {% endif %}')
    L.append('    {% else %}')
    L.append('        RESPOND MSG="' + canon + ' is not in this file"')
    L.append('    {% endif %}')
    L.append('')
    # ---- accel ----
    L.append('[menu __main ' + parent + ' __feat __' + sid + ' __acc]')
    L.append('type: input')
    L.append("name: Acc: {'%5d' % menu.input}")
    L.append('input: {' + SV + '.ovf_' + code + '_acc|default(0)}')
    L.append('input_min: 0')
    L.append('input_max: 20000')
    L.append('input_step: 100')
    L.append('gcode:')
    L.append('    {% set s = ' + ST + ' %}')
    L.append('    {% if ' + avail(canon) + ' %}')
    L.append('        SET_OVERRIDE_VALUE NAME=feat_acc_' + code + ' VALUE={menu.input|round|int}')
    if live:
        L.append("        {% if s.current_type|default('') == '" + canon + "' %}")
        L.append('            APPLY_TYPE TYPE=' + canon)
        L.append('        {% endif %}')
    L.append('    {% else %}')
    L.append('        RESPOND MSG="' + canon + ' is not in this file"')
    L.append('    {% endif %}')
    if code == 'ironing':
        L.append('')
        L.append('[menu __main ' + parent + ' __feat __ir __fl]')
        L.append('type: input')
        L.append("name: Flow: {'%3d' % menu.input} %")
        L.append('input: {' + SV + '.ov_ironing_flow|default(100)}')
        L.append('input_min: 10')
        L.append('input_max: 150')
        L.append('input_step: 5')
        L.append('gcode:')
        L.append('    {% set s = ' + ST + ' %}')
        L.append("    {% if s.file_types|default('') == '' or 'IRONING' in s.file_types %}")
        L.append('        SET_OVERRIDE_VALUE NAME=ironing_flow VALUE={menu.input|round|int}')
        if live:
            L.append("        {% if s.current_type|default('') == 'IRONING' %}")
            L.append('            APPLY_TYPE TYPE=IRONING')
            L.append('        {% endif %}')
        L.append('    {% else %}')
        L.append('        RESPOND MSG="IRONING is not in this file"')
        L.append('    {% endif %}')
    L.append('')
    return '\n'.join(L)

def feats_block(parent, live):
    B = ['# ---- R60: 12 features, only the ones the file really contains are editable ----',
         '[menu __main ' + parent + ' __feat]',
         'type: list',
         'name: Features',
         '']
    for sid, code, canon, pfx in FEATS:
        B.append(feat_submenu(parent, sid, code, canon, live))
    return '\n'.join(B)

def activators(parent, live):
    B = ['# ---- R60: click = activate (OFF resets to the file original) ----']
    for sid, code, canon, pfx in FEATS:
        B.append('[menu __main ' + parent + ' __file __ac' + AC_ID[sid] + ']')
        B.append('type: command')
        B.append('name: ' + pfx + ':{' + fs_name(code) + "} {'o:ON' if " + SV + '.ovf_' + code + "_on|default(False) else 'o:--'}")
        B.append('gcode:')
        B.append('    {% set s = ' + ST + ' %}')
        B.append('    {% if ' + avail(canon) + ' %}')
        B.append('        SET_OVERRIDE_VALUE NAME=feat_on_' + code + ' VALUE={1 if not ' +
                 SV + '.ovf_' + code + '_on|default(False) else 0}')
        msg = "'ON - edit the percent in Features' if not " + SV + '.ovf_' + code + "_on|default(False) else 'OFF - back to the file original'"
        B.append('        RESPOND MSG="[Feature] ' + code.upper() + ' {' + msg + '}"')
        if live:
            B.append("        {% if s.current_type|default('') == '" + canon + "' %}")
            B.append('            APPLY_TYPE TYPE=' + canon)
            B.append('        {% endif %}')
        B.append('    {% else %}')
        B.append('        RESPOND MSG="' + canon + ' is not in this file - nothing to override"')
        B.append('    {% endif %}')
        B.append('')
    return '\n'.join(B)

# ================= 1) Pre-Print __feat komplett neu =================
a = t.index('[menu __main __preprint __feat]')
b = t.index('[menu __main __preprint __flow]')
t = t[:a] + feats_block('__preprint', live=False) + '\n' + t[b:]

# ================= 2) Live __feats neu (vor __extr) =================
i = t.index('\n[menu __main __live __extr]')
t = t[:i] + '\n' + feats_block('__live', live=True) + t[i:]

# ================= 3) Pre-Print __file: __spd/__acc neu + Aktivierer neu =================
old_spd = """[menu __main __preprint __file __spd]
type: command
name: Spd: {printer['gcode_macro _STATE'].file_speed_outer|default(0)|int if printer['gcode_macro _STATE'].file_speed_outer|default(0) > 0 else '?'}mm/s
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File speeds mm/s: outer {s.file_speed_outer} | inner {s.file_speed_inner} | sparse {s.file_speed_sparse} | top {s.file_speed_top} | first layer {s.file_speed_first} | travel {s.file_speed_travel} | support {s.file_speed_support} | ironing {s.file_speed_ironing} - per-feature overwrites: Pre-Print > Outer Wall / Support / Ironing\""""
spd_list = ' | '.join([BY_CODE[c][2].split('-')[-1].lower() if '-' not in BY_CODE[c][2] else BY_CODE[c][2].replace('-', ' ').lower() for _, c, _, _ in FEATS])
fs_list = ' | '.join(['{s.file_feat_spd_' + c + '|default(0)|round|int} ' + pfx for _, c, _, pfx in FEATS])
new_spd = """[menu __main __preprint __file __spd]
type: command
name: Spd: {(printer['gcode_macro _STATE'].file_feat_spd_wallouter|default(0)|round|int|string ~ 'mm/s') if printer['gcode_macro _STATE'].file_feat_spd_wallouter|default(0) > 0 else '?'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File speeds mm/s (MEASURED from the g-code, feature by feature): outer wall {s.file_feat_spd_wallouter|default(0)|round|int} | inner wall {s.file_feat_spd_wallinner|default(0)|round|int} | sparse {s.file_feat_spd_infillsparse|default(0)|round|int} | solid {s.file_feat_spd_infillsolid|default(0)|round|int} | top {s.file_feat_spd_surfacetop|default(0)|round|int} | bottom {s.file_feat_spd_surfacebottom|default(0)|round|int} | bridge {s.file_feat_spd_bridge|default(0)|round|int} | gaps {s.file_feat_spd_gaps|default(0)|round|int} | support {s.file_feat_spd_support|default(0)|round|int} | ironing {s.file_feat_spd_ironing|default(0)|round|int} | skirt {s.file_feat_spd_skirt|default(0)|round|int} | brim {s.file_feat_spd_brim|default(0)|round|int} | first layer {s.file_speed_first} | travel {s.file_speed_travel} (config) - per-feature overrides: Features menu\""""
assert t.count(old_spd) == 1, 'spd anchor'
t = t.replace(old_spd, new_spd)

old_acc = """[menu __main __preprint __file __acc]
type: command
name: Acc: {printer['gcode_macro _STATE'].file_accel_outer|default(0)|int if printer['gcode_macro _STATE'].file_accel_outer|default(0) > 0 else '?'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File accels mm/s2: default {s.file_accel_default} | outer {s.file_accel_outer} | inner {s.file_accel_inner} | sparse {s.file_accel_sparse} | top {s.file_accel_top} - global overwrite: Pre-Print > Motion, per-feature: Outer Wall / Support\""""
new_acc = """[menu __main __preprint __file __acc]
type: command
name: Acc: {printer['gcode_macro _STATE'].file_feat_acc_wallouter|default(0)|round|int if printer['gcode_macro _STATE'].file_feat_acc_wallouter|default(0) > 0 else '?'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File accels mm/s2 (M204 measured per feature): outer {s.file_feat_acc_wallouter|default(0)|round|int} | inner {s.file_feat_acc_wallinner|default(0)|round|int} | sparse {s.file_feat_acc_infillsparse|default(0)|round|int} | solid {s.file_feat_acc_infillsolid|default(0)|round|int} | top {s.file_feat_acc_surfacetop|default(0)|round|int} | bottom {s.file_feat_acc_surfacebottom|default(0)|round|int} | bridge {s.file_feat_acc_bridge|default(0)|round|int} | gaps {s.file_feat_acc_gaps|default(0)|round|int} | support {s.file_feat_acc_support|default(0)|round|int} | ironing {s.file_feat_acc_ironing|default(0)|round|int} | skirt {s.file_feat_acc_skirt|default(0)|round|int} | brim {s.file_feat_acc_brim|default(0)|round|int} (0 = the file sends no M204 there) - global: Pre-Print > Motion\""""
assert t.count(old_acc) == 1, 'acc anchor'
t = t.replace(old_acc, new_acc)

# Aktivierer ersetzen: von '# ---- R59: click' bis __noz
a = t.index('# ---- R59: click = activate')
b = t.index('[menu __main __preprint __file __noz]')
t = t[:a] + activators('__preprint', live=False) + '\n' + t[b:]

open(P, 'w').write(t)
print('PASS 1+2+3 OK (Pre-Print __feat neu, Live __feats neu, Pre-Print File spd/acc/aktivierer neu)')
