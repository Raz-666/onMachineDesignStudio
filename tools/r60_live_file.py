#!/usr/bin/env python3
"""R60 step 4: Live > File (G-code) = full mirror of the Pre-Print file info + activators."""
import re

P = 'menus/lcd_menues.cfg'
t = open(P).read()

FEATS = [
    ('ow', 'wallouter',     'WALL-OUTER',     'OW', 'wall'),
    ('iw', 'wallinner',     'WALL-INNER',     'IW', 'walli'),
    ('sp', 'infillsparse',  'INFILL-SPARSE',  'SP', 'infi'),
    ('so', 'infillsolid',   'INFILL-SOLID',   'SO', 'solid'),
    ('tp', 'surfacetop',    'SURFACE-TOP',    'TP', 'surf'),
    ('bt', 'surfacebottom', 'SURFACE-BOTTOM', 'BT', 'surfb'),
    ('br', 'bridge',        'BRIDGE',         'BR', 'brid'),
    ('gp', 'gaps',          'GAPS',           'GP', 'gaps'),
    ('su', 'support',       'SUPPORT',        'SU', 'supp'),
    ('ir', 'ironing',       'IRONING',        'IR', 'iron'),
    ('sk', 'skirt',         'SKIRT',          'SK', 'skir'),
    ('bm', 'brim',          'BRIM',           'BM', 'brim'),
]
ST = "printer['gcode_macro _STATE']"
SV = "printer['save_variables'].variables"

def notin(canon):
    return ST + ".file_types|default('') != '' and '" + canon + "' not in " + ST + '.file_types'
def avail(canon):
    return 's.file_types' + "|default('') == '' or '" + canon + "' in s.file_types"
def fs_name(code):
    canon = dict((c, cn) for _, c, cn, _, _ in FEATS)[code]
    return ('(' + ST + '.file_feat_spd_' + code + "|default(0)|round|int|string ~ 'mm/s') if " + ST +
            '.file_feat_spd_' + code + "|default(0) > 0 else ('n/a' if " + notin(canon) + " else '--')")

B = []
B.append('# =====================================================================================')
B.append('#  LIVE > FILE (G-code) - R60: the FULL file info (like Pre-Print > File),')
B.append('#  measured originals + click-to-activate, usable DURING the print')
B.append('# =====================================================================================')
B.append('[menu __main __live __file]')
B.append('type: list')
B.append('name: File (G-code)')
B.append('')
B.append("""[menu __main __live __file __t]
type: command
name: File: {("MARKED" if printer['gcode_macro _STATE'].file_type|default("unknown") == "marked" else "LEGACY" if printer['gcode_macro _STATE'].file_type|default("unknown") == "legacy" else "?")}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File type: {s.file_type|default('unknown')|upper} - MARKED = R2 markers, LEGACY = no PRINT_START | features in this file: {s.file_types|default('unknown')}\"""")
B.append("""
[menu __main __live __file __m]
type: command
name: Mat: {printer['gcode_macro _STATE'].file_material|default('?')}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File material: {s.file_material} | your material: {printer['save_variables'].variables.material|default('PLA')}\"""")
B.append("""
[menu __main __live __file __ly]
type: command
name: Ly: {printer['gcode_macro _STATE'].file_layer_height|round(2)}x{printer['gcode_macro _STATE'].total_layers|default(0)|int if printer['gcode_macro _STATE'].total_layers|default(0) > 0 else '?'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File: layer height {s.file_layer_height} | {s.total_layers} layers (from the slicer) | by object: {'YES - sequential' if s.file_by_object|default(False) else 'no - by layer'}\"""")
B.append("""
[menu __main __live __file __lw]
type: command
name: W: {printer['gcode_macro _STATE'].file_line_width|default(0)|round(2) if printer['gcode_macro _STATE'].file_line_width|default(0) > 0 else '?'}mm
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File line width: {s.file_line_width}mm | first layer {s.file_line_width_first}mm | outer wall {s.file_line_width_wall}mm - from the slicer (post-processor)\"""")
B.append("""
[menu __main __live __file __fr]
type: command
name: FlowR: {printer['gcode_macro _STATE'].file_flow_ratio|round(2) if printer['gcode_macro _STATE'].file_flow_ratio|default(0) > 0 else '?'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File flow ratio: {s.file_flow_ratio} (slicer extrusion multiplier) | LIVE flow: {(printer.gcode_move.extrude_factor|default(1)*100)|round|int}%\"""")
B.append("""
[menu __main __live __file __spd]
type: command
name: Spd: {(printer['gcode_macro _STATE'].file_feat_spd_wallouter|default(0)|round|int|string ~ 'mm/s') if printer['gcode_macro _STATE'].file_feat_spd_wallouter|default(0) > 0 else '?'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File speeds mm/s (MEASURED): outer wall {s.file_feat_spd_wallouter|default(0)|round|int} | inner {s.file_feat_spd_wallinner|default(0)|round|int} | sparse {s.file_feat_spd_infillsparse|default(0)|round|int} | solid {s.file_feat_spd_infillsolid|default(0)|round|int} | top {s.file_feat_spd_surfacetop|default(0)|round|int} | bottom {s.file_feat_spd_surfacebottom|default(0)|round|int} | bridge {s.file_feat_spd_bridge|default(0)|round|int} | gaps {s.file_feat_spd_gaps|default(0)|round|int} | support {s.file_feat_spd_support|default(0)|round|int} | ironing {s.file_feat_spd_ironing|default(0)|round|int} | skirt {s.file_feat_spd_skirt|default(0)|round|int} | brim {s.file_feat_spd_brim|default(0)|round|int} - overrides: Live > Features\"""")
B.append("""
[menu __main __live __file __acc]
type: command
name: Acc: {printer['gcode_macro _STATE'].file_feat_acc_wallouter|default(0)|round|int if printer['gcode_macro _STATE'].file_feat_acc_wallouter|default(0) > 0 else '?'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File accels mm/s2 (M204 measured): outer {s.file_feat_acc_wallouter|default(0)|round|int} | inner {s.file_feat_acc_wallinner|default(0)|round|int} | sparse {s.file_feat_acc_infillsparse|default(0)|round|int} | solid {s.file_feat_acc_infillsolid|default(0)|round|int} | top {s.file_feat_acc_surfacetop|default(0)|round|int} | bottom {s.file_feat_acc_surfacebottom|default(0)|round|int} | bridge {s.file_feat_acc_bridge|default(0)|round|int} | gaps {s.file_feat_acc_gaps|default(0)|round|int} | support {s.file_feat_acc_support|default(0)|round|int} | ironing {s.file_feat_acc_ironing|default(0)|round|int} | skirt {s.file_feat_acc_skirt|default(0)|round|int} | brim {s.file_feat_acc_brim|default(0)|round|int} - overrides: Live > Features\"""")
B.append('')
B.append('# ---- R60: click = activate (OFF resets to the file original) ----')
for sid, code, canon, pfx, acid in FEATS:
    B.append('[menu __main __live __file __ac' + acid + ']')
    B.append('type: command')
    B.append('name: ' + pfx + ':{' + fs_name(code) + "} {'o:ON' if " + SV + '.ovf_' + code + "_on|default(False) else 'o:--'}")
    B.append('gcode:')
    B.append('    {% set s = ' + ST + ' %}')
    B.append('    {% if ' + avail(canon) + ' %}')
    B.append('        SET_OVERRIDE_VALUE NAME=feat_on_' + code + ' VALUE={1 if not ' + SV + '.ovf_' + code + '_on|default(False) else 0}')
    B.append('        RESPOND MSG="[Feature] ' + code.upper() + ' ' + "'ON - edit in Features' if not " + SV + '.ovf_' + code + "_on|default(False) else 'OFF - back to the file original'" + '"')
    B.append("        {% if s.current_type|default('') == '" + canon + "' %}")
    B.append('            APPLY_TYPE TYPE=' + canon)
    B.append('        {% endif %}')
    B.append('    {% else %}')
    B.append('        RESPOND MSG="' + canon + ' is not in this file - nothing to override"')
    B.append('    {% endif %}')
    B.append('')
B.append("""[menu __main __live __file __noz]
type: command
name: Noz: {printer['gcode_macro _STATE'].file_nozzle|round(2) if printer['gcode_macro _STATE'].file_nozzle|default(0) > 0 else '?'} W{printer['gcode_macro _STATE'].file_wall_loops|default(0)|int}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File nozzle: {s.file_nozzle}mm | wall loops: {s.file_wall_loops} - from the slicer (post-processor)\"""")
B.append("""
[menu __main __live __file __h]
type: command
name: Hot: {printer['gcode_macro _STATE'].file_hotend_first|round(0)|int}/{printer['gcode_macro _STATE'].file_hotend_after|round(0)|int}C
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File hotend: L1 {s.file_hotend_first}C / L2 {s.file_hotend_after}C -> live change: Live Tuning > Hot, overrides: Pre-Print > Temps\"""")
B.append("""
[menu __main __live __file __b]
type: command
name: Bed: {printer['gcode_macro _STATE'].file_bed|round(0)|int}/{printer['gcode_macro _STATE'].file_bed_after|round(0)|int}C
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File bed: L1 {s.file_bed}C / L2 {s.file_bed_after}C -> live change: Live Tuning > Bed, overrides: Pre-Print > Temps\"""")
B.append("""
[menu __main __live __file __p]
type: command
name: PA: {printer['gcode_macro _STATE'].file_pa if printer['gcode_macro _STATE'].file_pa|default(0) > 0 else '-'}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File pressure advance: {s.file_pa} -> your LIVE PA: Live Tuning > Extrusion\"""")
B.append("""
[menu __main __live __file __r]
type: command
name: Ret: {printer['gcode_macro _STATE'].file_retract_len if printer['gcode_macro _STATE'].file_retract_len|default(0) > 0 else '-'}@{printer['gcode_macro _STATE'].file_retract_speed|default(0)|int}
gcode:
    {% set s = printer['gcode_macro _STATE'] %}
    RESPOND MSG="File retraction: {s.file_retract_len}mm @ {s.file_retract_speed}mm/s -> live change: Live Tuning > Extrusion\"""")
B.append("""
[menu __main __live __file __f]
type: command
name: File F: {(printer['gcode_macro _STATE'].file_fan * 100 // 255)|int}%
gcode:
    RESPOND MSG="File fan: S{printer['gcode_macro _STATE'].file_fan|int} ({(printer['gcode_macro _STATE'].file_fan * 100 // 255)|int}% of S255)\"""")
B.append("""
[menu __main __live __file __fl]
type: command
name: File Fl: {printer['gcode_macro _STATE'].file_flow|round(0)|int}%
gcode:
    RESPOND MSG="File flow factor: {printer['gcode_macro _STATE'].file_flow|round(1)}% (M221 from the file)\"""")
B.append("""
[menu __main __live __file __a]
type: command
name: File A: {printer['gcode_macro _STATE'].file_accel|round(0)|int if printer['gcode_macro _STATE'].file_accel > 0 else 'n/a'}
gcode:
    RESPOND MSG="File acceleration: {printer['gcode_macro _STATE'].file_accel|round(0)|int} mm/s2 (M204 from the file)\"""")
B.append('')

new_block = '\n'.join(B)
a = t.index('[menu __main __live __file]')
b = t.index('[menu __main __live __chot]')
t = t[:a] + new_block + t[b:]
open(P, 'w').write(t)
print('Live > File Spiegel OK')
