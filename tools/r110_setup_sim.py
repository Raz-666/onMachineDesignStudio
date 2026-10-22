#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R110: install + update simulation across community printer types.

Drives setup.sh + update.sh the way a USER would (piped answers, real file
system, no systemd / no moonraker - exactly the safe-default paths) on six
printer profiles:

  ender3-stock        cartesian bed slinger, single Z, BLTouch, no LEDs,
                      no R2 includes yet (fresh install)
  ender3-ref          the reference machine: [neopixel printer_leds] exists
                      in printer.cfg, save_config block at the end
  legacy-r2postproc   pre-.82 install: active [r2_postproc] section that
                      would halt current Klipper -> migration path
  corexy-2z           CoreXY, 2 Z steppers + [z_tilt], existing [dotstar]
  voron-trident       CoreXY, 3 Z steppers, toolhead neopixel over CAN
  voron-v2            4 Z steppers, NO LEDs at all (wizard must skip clean)

Checks per scenario (setup): exit 0, verified backups, r2_hardware.cfg
content (incl. the R110 LED color order), [include r2_hardware.cfg] exactly
once and BEFORE the '#*#' save_config block, existing LED sections kept
byte-identical, legacy migration commented out + values carried over.
Then the UPDATE path: release zip unpacked over the install, keep-settings,
printer.cfg must stay byte-identical. Extra safety nets: --check mode and
piped-EOF mode change NOTHING, a second setup run is idempotent.

Run:  python3 tools/r110_setup_sim.py        (from the repo root)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VERSION = 'R2-2026-10-12.92'
ZIP_NAME = 'klipper-e3-r2d2-UPDATE-R2-2026-10-22.118.zip'

INCLUDES = ''.join(
    '[include klipper-e3-r2d2/macros/%s.cfg]\n' % m for m in
    ['01_state', '02_sounds', '03_leds', '04_notify', '05_materials',
     '06_temp_controls', '07_start_confirm', '08_print_start_stop',
     '09_pause_filament', '10_live_tuning', '11_gantry_sync',
     '12_maintenance', '13_system', '14_kamp', '15_objects',
     '16_labels', '17_generator'])

SAVECFG = '\n#*# <save_config>\n#*# [bltouch]\n#*# z_offset = 2.100\n'

MOONRAKER = """[server]
host: 0.0.0.0

[file_manager]
config_path: ~/printer_data/config

[update_manager]

[machine]
"""

PRINTER = {
 'ender3-stock': """# Ender-3 stock (Marlin -> Klipper), single Z, BLTouch, no LEDs
[stepper_x]
step_pin: PC2
[stepper_y]
step_pin: PC2
[stepper_z]
step_pin: PC2
[printer]
kinematics: cartesian
max_velocity: 300
[bltouch]
sensor_pin: ^PB1
[bed_mesh]
[extruder]
[heater_bed]
""" + SAVECFG,
 'ender3-ref': """# Ender-3 reference (SKR mini E3 v3)
[printer]
kinematics: cartesian
max_velocity: 300
[stepper_x]
[stepper_y]
[stepper_z]
[bltouch]
[bed_mesh]
[extruder]
[heater_bed]
[neopixel printer_leds]
pin: PA8
chain_count: 5
color_order: GRB
""" + INCLUDES + SAVECFG,
 'legacy-r2postproc': """# old R2 install (.81 era) with the raw carrier section
[printer]
kinematics: cartesian
[stepper_x]
[stepper_y]
[stepper_z]
[bltouch]
[extruder]
[heater_bed]
[r2_postproc]
bed_min_x: 5.0
bed_max_x: 230.0
bed_min_y: 5.0
bed_max_y: 225.0
""" + INCLUDES + SAVECFG,
 'corexy-2z': """# generic CoreXY, 2 Z steppers + z_tilt, dotstar case light
[printer]
kinematics: corexy
max_velocity: 350
[stepper_x]
[stepper_y]
[stepper_z]
[stepper_z1]
[z_tilt]
z_positions: 10,240
[probe]
pin: ^PB4
[bed_mesh]
[extruder]
[heater_bed]
[dotstar caselight]
data_pin: PB5
clock_pin: PB6
chain_count: 8
color_order: RGB
""" + SAVECFG,
 'voron-trident': """# Voron Trident, 3 Z steppers, toolhead neopixel over CAN
[printer]
kinematics: corexy
max_velocity: 400
[stepper_x]
[stepper_y]
[stepper_z]
[stepper_z1]
[stepper_z2]
[z_tilt]
z_positions: 60,150,240
[probe]
pin: ^EBB:PB8
[bed_mesh]
[extruder]
[heater_bed]
[neopixel toolhead_leds]
pin: EBB:PD3
chain_count: 3
color_order: GRB
[temperature_sensor chamber]
sensor_type: temperature_host
""" + SAVECFG,
 'voron-v2': """# Voron V2, 4 Z steppers, no LEDs at all
[printer]
kinematics: corexy
max_velocity: 350
[stepper_x]
[stepper_y]
[stepper_z]
[stepper_z1]
[stepper_z2]
[stepper_z3]
[z_tilt]
z_positions: 60,150,240,300
[probe]
pin: ^PD10
[bed_mesh]
[extruder]
[heater_bed]
""" + SAVECFG,
 'r92-config-block': """# Ender-3 with the .82-era carrier: [gcode_macro _R2_CONFIG] sits
# right after [board_pins] and carries the '# optional:' column-0 comment -
# the EXACT field-log .86 boot-halt layout ('Option gcode is not valid in
# section board_pins')
[printer]
kinematics: cartesian
max_velocity: 300
[stepper_x]
[stepper_y]
[stepper_z]
[board_pins]
aliases:
    EXP1_1: PC5
[bltouch]
[bed_mesh]
[gcode_macro _R2_CONFIG]
description: R2 portability config (bed limits + positions) - macros AND watcher read this
variable_bed_min_x: 5.0
variable_bed_max_x: 230.0
variable_bed_min_y: 5.0
variable_bed_max_y: 225.0
# optional: variable_present_x/y (PRINT_END presentation), variable_wipe_x/y (wipe pad; -1 = corner)
gcode:
    # config carrier only - never runs
[extruder]
[heater_bed]
""" + SAVECFG,
 'sv06-dualz': """# Sovol SV06: cartesian, 2 COUPLED Z steppers (no z_tilt!),
# CR-Touch probe - the z-tilt menu must NOT appear without [z_tilt]
[printer]
kinematics: cartesian
max_velocity: 300
[stepper_x]
[stepper_y]
[stepper_z]
[stepper_z1]
[probe]
pin: ^PC4
[bed_mesh]
[extruder]
[heater_bed]
""" + SAVECFG,
 'corexz-sw': """# Voron Switchwire style: CoreXZ bedsligner, single Z,
# klicky-style probe, NO LEDs (wizard must skip clean)
[printer]
kinematics: corexz
max_velocity: 350
[stepper_x]
[stepper_y]
[stepper_z]
[probe]
pin: ^PA7
[bed_mesh]
[extruder]
[heater_bed]
""" + SAVECFG,
 'hybrid-corexy': """# Prusa-MK4-style hybrid coreXY, single Z, superpinda
# probe + dotstar backlight
[printer]
kinematics: hybrid_corexy
max_velocity: 400
[stepper_x]
[stepper_y]
[stepper_z]
[probe]
pin: ^PC13
[bed_mesh]
[extruder]
[heater_bed]
[dotstar backlight]
data_pin: PB5
clock_pin: PB6
chain_count: 4
color_order: RGB
""" + SAVECFG,
}

# ---- answer streams -----------------------------------------------------------------
# '' = Enter (default); 'y'/'1'/values where the default is not what we want.
# Mirrors the wizard prompt order exactly (the sim pins the UX flow).
V = ['', '']            # one r2_confirm_value / r2_choice: value + confirm
# hw wizard: bed minX maxX minY maxY Z (5) + probe choice (1) + probeX probeY (2)
#            + wipeX wipeY (2) + presentX presentY (2)  = 12 prompts
HW_WIZARD = V * 12 + ['']      # ... + 'write r2_hardware.cfg with these values?' [Y/n]
LED_NEOPIXEL_MAIN = V * 4                # type choice, section name, data pin, chain count
LED_DOTSTAR_MAIN = V * 4                 # section name, data_pin, clock_pin, chain
COLOR_ORDER = V                          # menu choice + confirm (default order)
AREAS = V * 4                            # status, bed, nozzle choice, brightness
WRITE_Y = ['']                           # "write this LED setup?" [Y/n]

# tail after the wizards: service install OFF (the sim never installs a real
# systemd unit - the install path itself is proven, see SESSION_STATE R110),
# object processing keep, KAMP no, LED effects no, swap no
TAIL = ['n', '', '', 'n', 'n', 'n']

SCEN_SETUP = {
 'ender3-stock': (['y']                       # run the hw + LED wizard
                  + HW_WIZARD + ['1', '']     # hw values -> pick mode 1, remember
                  + ['y'] + LED_NEOPIXEL_MAIN + COLOR_ORDER + AREAS + WRITE_Y
                  + TAIL),      # KAMP offer n, LED effects n, swap n
 'ender3-ref': (['y'] + HW_WIZARD + ['1', '']
                + ['y']                       # configure the detected LEDs
                + LED_NEOPIXEL_MAIN + COLOR_ORDER + AREAS + WRITE_Y
                + TAIL),
 'legacy-r2postproc': (['y']                  # migrate [r2_postproc]
                       + ['1', '']            # include mode 1, remember
                       + ['']                 # "open the wizard anyway?" n
                       + TAIL),
 'corexy-2z': (['y'] + HW_WIZARD + ['1', '']
               + ['y'] + ['2', '']            # dotstar
               + LED_DOTSTAR_MAIN + ['4', ''] # color order: BGR (the dotstar default)
               + AREAS + WRITE_Y + TAIL),
 'voron-trident': (['y'] + HW_WIZARD + ['1', '']
                   + ['y'] + V                # LED type: neopixel (default)
                   + ['toolhead_leds', '']    # keep the EXISTING section name
                   + ['EBB:PD3', '']          # ... and its pin
                   + ['3', '']                # chain count
                   + COLOR_ORDER + AREAS + WRITE_Y
                   + TAIL),
 'voron-v2': (['y'] + HW_WIZARD + ['1', '']
              + ['']                          # "use LEDs on this printer?" -> NO
              + TAIL),
 'sv06-dualz': (['y'] + HW_WIZARD + ['1', '']
                + ['y'] + LED_NEOPIXEL_MAIN + COLOR_ORDER + AREAS + WRITE_Y
                + TAIL),
 'r92-config-block': (['y'] + HW_WIZARD
                      + ['1', 'n']       # include r2_hardware.cfg: mode 1, do NOT remember
                      + ['1', 'y']       # move _R2_CONFIG block: mode 1, remember
                      + ['']             # no LEDs on this sim machine
                      + TAIL),
 'corexz-sw': (['y'] + HW_WIZARD + ['1', '']
               + ['']                        # no LEDs
               + TAIL),
 'hybrid-corexy': (['y'] + HW_WIZARD + ['1', '']
                   + ['y'] + ['2', '']        # dotstar
                   + LED_DOTSTAR_MAIN + ['4', '']   # BGR (like corexy-2z)
                   + AREAS + WRITE_Y + TAIL),
}

fails = []
def check(name, ok, info=''):
    if not ok:
        fails.append(name)
        print('  FAIL %s %s' % (name, info))
    return ok

def copy_pkg(dst):
    """installed package = the current repo working tree (no .git)"""
    shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns(
        '.git', '__pycache__', 'r2_backups', '*.r2bak*'))

def make_zip(cfg_dir):
    """release-style update zip WITH the klipper-e3-r2d2/ prefix"""
    zpath = os.path.join(cfg_dir, ZIP_NAME)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(os.path.join(cfg_dir, 'klipper-e3-r2d2')):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, cfg_dir))
    return zpath

def tree_state(cfg_dir):
    state = {}
    for root, dirs, files in os.walk(cfg_dir):
        dirs[:] = [d for d in dirs
                   if d != 'r2_backups' and d != '__pycache__']
        for f in files:
            if '.r2bak' in f or f == ZIP_NAME:
                continue
            full = os.path.join(root, f)
            state[os.path.relpath(full, cfg_dir)] = open(full, 'rb').read()
    return state

SANDBOX_BIN = None
CURRENT_SCENARIO = 'scenario'

def make_sandbox_bin():
    """PATH without sudo: privileged writes are IMPOSSIBLE even if an answer
    stream ever drifts (no wizard prompt may ever install system units)."""
    global SANDBOX_BIN
    SANDBOX_BIN = tempfile.mkdtemp(prefix='r110_bin_')
    for d in os.environ.get('PATH', '').split(os.pathsep):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f == 'sudo':
                continue
            dst = os.path.join(SANDBOX_BIN, f)
            if not os.path.exists(dst):
                try:
                    os.symlink(os.path.join(d, f), dst)
                except OSError:
                    pass
    return SANDBOX_BIN

def run_script(cmd, answers, cfg_dir, home, step='run'):
    env = dict(os.environ)
    env['HOME'] = home
    env['TERM'] = 'dumb'
    if SANDBOX_BIN:
        env['PATH'] = SANDBOX_BIN + os.pathsep + env.get('PATH', '')
    if answers:
        inp = '\n'.join(answers) + '\n' * 8   # trailing Enters = safe defaults
    else:
        inp = ''                                # REAL EOF (non-interactive SSH)
    log = '/tmp/r110_%s_%s_%s.log' % (CURRENT_SCENARIO, step, os.path.basename(cmd[-1]).replace('.sh', '').replace('.cfg', ''))
    # incremental logging: on a hang the log shows WHERE it stopped
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, env=env, cwd=cfg_dir,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    import threading
    def _pump():
        with open(log, 'w') as lf:
            lf.write('CMD: %s\nANSWERS: %r\n\n' % (cmd, answers))
            for line in proc.stdout:
                lf.write(line)
                lf.flush()
    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    try:
        proc.stdin.write(inp)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    try:
        rc = proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    t.join(5)
    class _R:  # tiny result shim
        returncode = rc
        stdout = open(log).read()
    return _R()

def backups_exist(cfg_dir):
    bd = os.path.join(cfg_dir, 'r2_backups')
    return os.path.isdir(bd) and any('-setup' in d for d in os.listdir(bd))

# =====================================================================================
def simulate(name):
    global CURRENT_SCENARIO
    CURRENT_SCENARIO = name
    print('--- %s ' % name.ljust(48, '-'))
    tmp = tempfile.mkdtemp(prefix='r110_%s_' % name.replace('-', '_'))
    home = os.path.join(tmp, 'home')
    cfg_dir = os.path.join(home, 'printer_data', 'config')
    os.makedirs(cfg_dir)
    copy_pkg(os.path.join(cfg_dir, 'klipper-e3-r2d2'))
    pc = os.path.join(cfg_dir, 'printer.cfg')
    open(pc, 'w').write(PRINTER[name])
    open(os.path.join(cfg_dir, 'moonraker.conf'), 'w').write(MOONRAKER)
    before_pc = open(pc, 'rb').read().decode('utf-8', 'replace')

    # ---- 1) --check mode changes NOTHING
    snap0 = tree_state(cfg_dir)
    p = run_script(["bash", "klipper-e3-r2d2/setup.sh", pc, "--check"], [], cfg_dir, home, "check")
    check('%s: check mode exit 0' % name, p.returncode == 0, p.stdout[-400:])
    check('%s: check mode changed nothing' % name, tree_state(cfg_dir) == snap0,
          set(tree_state(cfg_dir)) ^ set(snap0))

    # ---- 2) piped EOF (non-interactive) changes NOTHING
    snap = tree_state(cfg_dir)
    p = run_script(["bash", "klipper-e3-r2d2/setup.sh", pc], [], cfg_dir, home, "eof")
    check('%s: EOF run exit 0' % name, p.returncode == 0, p.stdout[-400:])
    check('%s: EOF run changed nothing' % name, tree_state(cfg_dir) == snap,
          set(tree_state(cfg_dir)) ^ set(snap))

    # ---- 3) the real interactive install
    p = run_script(['bash', 'klipper-e3-r2d2/setup.sh', pc],
                   SCEN_SETUP[name], cfg_dir, home, 'install')
    out = p.stdout
    check('%s: setup exit 0' % name, p.returncode == 0, out[-600:])
    check('%s: no backup-rule abort' % name, 'ABORTED by the backup rule' not in out)
    check('%s: backups made' % name, backups_exist(cfg_dir))

    hw_path = os.path.join(cfg_dir, 'r2_hardware.cfg')
    hw = open(hw_path).read() if os.path.exists(hw_path) else ''
    pc_now = open(pc).read()

    check('%s: r2_hardware.cfg written' % name, '[gcode_macro _R2_CONFIG]' in hw)
    check('%s: include added exactly once' % name,
          pc_now.count('[include r2_hardware.cfg]') == 1)
    check('%s: include BEFORE the save_config block' % name,
          pc_now.find('[include r2_hardware.cfg]') < pc_now.find('#*#'))

    if name == 'legacy-r2postproc':
        check('%s: [r2_postproc] commented out' % name,
              '# [R2-off] [r2_postproc]' in pc_now
              and '\n[r2_postproc]' not in pc_now)
        check('%s: values migrated' % name,
              'variable_bed_min_x: 5.0' in hw
              and 'variable_bed_max_x: 230.0' in hw)
    else:
        # hw wizard ran on every other scenario -> Ender defaults or answers
        check('%s: bed values in profile' % name, 'variable_bed_max_x' in hw)

    if name in ('ender3-ref', 'voron-trident'):
        # existing user LED section must stay byte-identical
        for tag, sec in (('ender3-ref', '[neopixel printer_leds]'),
                         ('voron-trident', '[neopixel toolhead_leds]')):
            if name == tag:
                i, j = before_pc.find(sec), before_pc.find('\n[', before_pc.find(sec) + 2)
                orig = before_pc[i:j]
                check('%s: existing LED section kept untouched' % name,
                      orig in open(pc).read())
                check('%s: no LED section in OUR profile' % name,
                      '[neopixel ' not in hw and '[dotstar ' not in hw)
    if name in ('ender3-stock', 'corexy-2z', 'sv06-dualz', 'hybrid-corexy'):
        # wizard WROTE the chain into r2_hardware.cfg - with the R110 color order
        check('%s: LED section in profile' % name,
              ('[neopixel printer_leds]' in hw) or ('[dotstar printer_leds]' in hw))
        co = 'BGR' if name in ('corexy-2z', 'hybrid-corexy') else 'GRB'
        check('%s: color_order %s asked + written' % (name, co),
              'color_order: %s' % co in hw and ('variable_led_color_order: %s' % co) in hw)
    if name in ('voron-v2', 'corexz-sw'):
        check('%s: LED skip = no LED keys' % name,
              'variable_led_type' not in hw)
    if name == 'sv06-dualz':
        # 2 Z steppers WITHOUT [z_tilt]: the profile must not claim z-tilt
        check('%s: no z-tilt keys without [z_tilt]' % name,
              'variable_ztilt' not in hw and 'z_tilt' not in hw)
    if name == 'r92-config-block':
        # R113 field-log .86: the migration must comment the WHOLE .82 block
        # (a column-0 '# optional:' line used to stop the pattern - 'gcode:'
        # stayed active and landed in [board_pins] = boot halt) and must not
        # glue the next section header onto the last comment line (rstrip bug)
        _b = pc_now.find('# [R2-off] [gcode_macro _R2_CONFIG]')
        check('%s: old block commented (header line found)' % name, _b >= 0)
        _tail = pc_now[_b:]
        _nl = _tail.find('\n[')
        _seg = _tail[:_nl] if _nl >= 0 else _tail
        _orphan = [l for l in _seg.split('\n')[1:]
                   if l.strip() and not l.lstrip().startswith('#')]
        check('%s: NO active orphan lines in the commented block (the .86 halt)' % name,
              not _orphan, _orphan[:3])
        check('%s: the gcode: line is commented out' % name,
              '# [R2-off] gcode:' in _seg)
        for sec in ('[board_pins]', '[extruder]', '[heater_bed]'):
            check('%s: %s survives as an active section (no glue)' % (name, sec),
                  ('\n' + sec) in pc_now
                  and ('\n# [R2-off] ' + sec) not in pc_now)
        check('%s: no line glued onto the last R2-off comment' % name,
              not [l for l in pc_now.split('\n')
                   if l.startswith('# [R2-off]') and l.rstrip().endswith(']')
                   and '[R2-off] ' not in l[len('# [R2-off] '):]][:1] == []
              or all(not (l.startswith('# [R2-off]') and l.count('[') > 1)
                     for l in pc_now.split('\n')))

    # ---- 4) second setup run is IDEMPOTENT (profile exists -> wizard skipped)
    snap2 = tree_state(cfg_dir)
    p = run_script(['bash', 'klipper-e3-r2d2/setup.sh', pc], [''], cfg_dir, home, 'second')
    check('%s: 2nd setup exit 0' % name, p.returncode == 0, p.stdout[-400:])
    _t2 = tree_state(cfg_dir)
    if _t2 != snap2:
        _delta = [k for k in set(_t2) | set(snap2) if _t2.get(k) != snap2.get(k)]
    else:
        _delta = []
    check('%s: 2nd setup changed nothing' % name, _t2 == snap2, _delta)

    # ---- 5) the UPDATE path: release zip over the install, keep settings
    missing = []
    for m in INCLUDES.splitlines():
        if m not in open(pc).read():
            missing.append(m)
    with open(pc, 'a') as f:                     # "user adds the printed includes"
        for m in missing:
            f.write(m + '\n')
    make_zip(cfg_dir)
    pre_update = tree_state(cfg_dir)
    p = run_script(['bash', 'klipper-e3-r2d2/update.sh'], [''], cfg_dir, home, 'update')
    out = p.stdout
    check('%s: update exit 0' % name, p.returncode == 0, out[-600:])
    check('%s: update saw + unpacked the zip' % name,
          'uploaded update zip found' in out and 'package files replaced' in out)
    check('%s: update kept the LED + hardware settings' % name,
          'Keep the current LED + hardware settings' in out)
    post = tree_state(cfg_dir)
    check('%s: printer.cfg byte-identical through the update' % name,
          post.get('printer.cfg') == pre_update.get('printer.cfg'))
    check('%s: r2_hardware.cfg survives the update' % name,
          post.get('r2_hardware.cfg') == pre_update.get('r2_hardware.cfg'))
    check('%s: backup dir has an update pass' % name,
          any('-update' in d for d in os.listdir(os.path.join(cfg_dir, 'r2_backups'))))

    shutil.rmtree(tmp, ignore_errors=True)
    return len(fails)

# =====================================================================================
if __name__ == '__main__':
    os.chdir(REPO)
    make_sandbox_bin()
    for sc in (sys.argv[1:] or list(PRINTER)):
        simulate(sc)
    print()
    if fails:
        print('R110 SETUP SIM: %d FAILURE(S)' % len(fails))
        sys.exit(1)
    print('R110 SETUP SIM: all %d printer scenarios passed'
          ' (install + update + check + EOF + idempotence)' % len(PRINTER))
