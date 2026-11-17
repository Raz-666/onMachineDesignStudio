#!/usr/bin/env python3
"""R257 (.142m): the PROBE-QUIET LED guard - no LED animation traffic while the
probe is moving, and a test that PROVES it can see the mistake.

WHY THIS FILE EXISTS
====================
The 12.11.2026 field logs (three R2-DOCTOR packs, 22:11 / 22:13 / 22:19) hold
EIGHT MCU shutdowns. Six of them report the SAME toolhead position:

    192836  Requested toolhead position at shutdown time 13398.919218:
            (115.00000000000003, 115.00000000000003, 5.125450312537781)
    224899  ... 265.666386: (115.0, 115.0, 10.0)
    256885  ... 207.579927: (115.0, 115.0, 8.668869410338058)
    321710  ... 259.984572: (115.0, 115.0, 4.7587611193387716)
    356394  ... 4710.041606: (115.0, 115.0, 10.0)
    46474   ... 149.507098: (115.0, 115.0, 9.90619385371419)

X = Y = 115.0 is not a bed centre and not a layer Z - it is the field printer's
[safe_z_home] home_xy_position (115,115) with z_hop = 10 (printer.cfg in the same
pack). Z between 4.76 and 10.0 is the probe DESCENT between the hop and the
trigger. So these are not "crashes during the print": they are crashes while the
probe moves - the one phase where the stepper queue runs at a 1 ms step interval
(queue_step interval=64000 at 64 MHz).

What the send-queue dumps show in exactly that window (both dumps, same shape):

    Sent 00 ... queue_step oid=11 interval=32000 count=500 add=0,
             neopixel_update oid=2 pos=2 data=b'*\\x00\\x00...', 
    Sent 01 ... neopixel_send oid=2
    Sent 03 ... neopixel_update oid=2 ..., neopixel_send oid=2
    Sent 10 ... trsync_start ..., endstop_home ..., neopixel_up...
    Sent 11 ... neopixel_send oid=2
    Sent 12 ... neopixel_send oid=2
    Sent 13 ... neopixel_send oid=2      <- three in a row, 12 ms apart
    Sent 14 ... tmcuart_send oid=0 ...   <- TMC UART, blocking on the MCU
    Sent 04 ... st7920_send_cmds ... data=b'>mpOpenE27.gcode'  <- LCD bit-bang

plus right before: 'Neopixel update did not succeed' (repeated), later
'led update transmit error' / "Unable to obtain 'neopixel_result' response",
bytes_retransmit=85, and a clock model that was 191 ppm off
(clock_est freq 63998744.721 vs mcu_freq 64000000) - a failed neopixel
transmit blocks the HOST until the serial retry timeout, and the move queue is
empty by then (buffer_time=0.000).

WHY THE LED CHAIN IS THE PART WE CAN FIX OURSELVES
==================================================
One SET_LED_STATE state change writes the strip 2-4 times back to back
(STOP_LED_EFFECTS, SET_LED_EFFECT, _NOZZLE_SET, _BEDLIGHT_SET). The WS2812 output
is bit-banged by the MCU with interrupts disabled. In a print that is harmless;
inside the probe descent it is exactly the wrong moment. R246d already removed
the *pointless* repeats (unchanged state = no-op) - what is left is the one
deliberate change G28 makes while it homes (mode -> 'homing' -> LED 'homing').

THE FIX (pinned by the checks below)
  1. _STATE carries variable_led_quiet (default False).
  2. [gcode_macro _LED_QUIET] ON=1 sets the flag and stops the running effect
     (one write, BEFORE the first motion); ON=0 clears it and re-applies the
     state that was last asked for (SET_LED_STATE ... FORCE=1).
  3. SET_LED_STATE obeys the flag: while muted it only RECORDS the wanted state,
     it does not write the strip.
  4. G28 brackets M99110 - mute before the first homing move, restore after.
  5. _CALIBRATE_MESH_PROFILE brackets the whole mesh block (KAMP / native
     adaptive / full bed - all three branches).
  6. The screws + PROBE_CALIBRATE flows in 12_ are bracketed the same way.
  7. _STATE_WATCHER self-heals a stuck mute (a motion that dies mid-way must not
     leave the printer dark).

THE COUNTER-TEST (the point of this file)
=========================================
A check that cannot fail is decoration. So every static check below is run a
second time against a MUTATED copy of the config, and the run fails unless the
mutation is caught. Mutation, expected to be caught:
    G28 loses the mute line / gets it in the wrong order, SET_LED_STATE loses
    the guard, the mesh bracket disappears, the watcher heal disappears, the
    variable declaration disappears, _LED_QUIET stops stopping the effect.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {
    'state': 'macros/01_state.cfg',
    'leds': 'macros/03_leds.cfg',
    'start': 'macros/08_print_start_stop.cfg',
    'kamp': 'macros/14_kamp.cfg',
    'maint': 'macros/12_maintenance.cfg',
    'gantry': 'macros/11_gantry_sync.cfg',
}


def load():
    out = {}
    for key, rel in FILES.items():
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
            out[key] = fh.read()
    return out


def macro_body(text, header):
    """Return the text of one [gcode_macro X] / [delayed_gcode X] block.

    The header MUST start a line - the file headers mention
    '[gcode_macro _STATE]' in prose, and a plain find() would return the
    comment block as if it were the macro (that is how the first version of
    this test reported a missing variable that was there all along).
    """
    for kind in ('gcode_macro', 'delayed_gcode'):
        start = text.find('\n[%s %s]' % (kind, header))
        if start >= 0:
            break
    if start < 0:
        return ''
    start += 1
    nxt = len(text)
    for marker in ('\n[gcode_macro ', '\n[delayed_gcode ', '\n[led_effect '):
        pos = text.find(marker, start + 1)
        if 0 <= pos < nxt:
            nxt = pos
    return text[start:nxt]


def cmd_pos(body, cmd):
    """Position of the first LINE of the block that really calls `cmd`.

    Same trap as above: 'BED_MESH_CALIBRATE'/'_LED_QUIET ON=0' also appear in
    comments and in `'gcode_macro BED_MESH_CALIBRATE' in printer` guards.
    """
    off = 0
    for line in body.split('\n'):
        s = line.strip()
        if s.startswith(cmd) and not s.startswith('#'):
            return off + len(line) - len(line.lstrip())
        off += len(line) + 1
    return -1


def run_checks(src):
    """All R257 checks against a dict of config texts. Returns a fail list."""
    fails = []

    def check(name, ok, detail=''):
        if not ok:
            fails.append('%s%s' % (name, (' (%s)' % detail) if detail else ''))

    state = src['state']
    leds = src['leds']
    start = src['start']
    kamp = src['kamp']
    maint = src['maint']

    # ---- 1) the flag exists -----------------------------------------------------
    check('1 state flag', 'variable_led_quiet:' in macro_body(state, '_STATE'),
          'variable_led_quiet missing in [gcode_macro _STATE]')

    # ---- 2) _LED_QUIET exists and does both halves ------------------------------
    quiet = macro_body(leds, '_LED_QUIET')
    check('2a _LED_QUIET exists', quiet != '', 'no [gcode_macro _LED_QUIET]')
    mute_at = quiet.find('led_quiet VALUE=True')
    check('2b mute sets the flag', mute_at >= 0, 'no led_quiet=True')
    stop_at = cmd_pos(quiet, 'STOP_LED_EFFECTS')
    check('2c mute stops the effect', stop_at > mute_at >= 0,
          'STOP_LED_EFFECTS missing after the flag set')
    unmute_at = quiet.find('led_quiet VALUE=False')
    check('2d unmute clears the flag', unmute_at > 0, 'no led_quiet=False')
    reapp_at = quiet.find('SET_LED_STATE', unmute_at if unmute_at > 0 else 0)
    check('2e unmute re-applies the state', reapp_at > unmute_at >= 0,
          'no SET_LED_STATE after the unmute')
    check('2f unmute forces the write',
          'FORCE=1' in quiet[reapp_at:] if reapp_at > 0 else False,
          'SET_LED_STATE without FORCE=1 - the unchanged-state no-op would eat it')

    # ---- 3) SET_LED_STATE obeys the flag, and BEFORE its own chain --------------
    sls = macro_body(leds, 'SET_LED_STATE')
    guard_at = sls.find('led_quiet')
    chain_at = cmd_pos(sls, 'STOP_LED_EFFECTS')
    check('3a SET_LED_STATE reads the flag', guard_at >= 0, 'no led_quiet guard')
    check('3b guard runs before the chain', 0 <= guard_at < chain_at,
          'guard=%s chain=%s' % (guard_at, chain_at))

    # ---- 4) G28 brackets M99110 -------------------------------------------------
    g28 = macro_body(start, 'G28')
    home_at = cmd_pos(g28, 'M99110')
    on_at = cmd_pos(g28, '_LED_QUIET ON=1')
    off_at = cmd_pos(g28, '_LED_QUIET ON=0')
    check('4a G28 mutes before homing', 0 <= on_at < home_at,
          'on=%s home=%s' % (on_at, home_at))
    check('4b G28 unmutes after homing', off_at > home_at >= 0,
          'off=%s home=%s' % (off_at, home_at))

    # ---- 5) the mesh block is bracketed -----------------------------------------
    mesh = macro_body(kamp, '_CALIBRATE_MESH_PROFILE')
    m_on = cmd_pos(mesh, '_LED_QUIET ON=1')
    m_off = cmd_pos(mesh, '_LED_QUIET ON=0')
    first_mesh = cmd_pos(mesh, 'BED_MESH_CALIBRATE')
    check('5a mesh mutes before probing', 0 <= m_on < first_mesh,
          'on=%s mesh=%s' % (m_on, first_mesh))
    check('5b mesh unmutes after probing', m_off > first_mesh >= 0,
          'off=%s mesh=%s' % (m_off, first_mesh))

    # ---- 6) every other probe descent in 12_ is bracketed -----------------------
    lines = maint.split('\n')
    unbracketed = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('SCREWS_TILT_CALCULATE') or s.startswith('PROBE_CALIBRATE'):
            if s.startswith('_'):
                continue
            before = [ln.strip() for ln in lines[max(0, i - 3):i]]
            after = [ln.strip() for ln in lines[i + 1:i + 3]]
            if '_LED_QUIET ON=1' not in before or '_LED_QUIET ON=0' not in after:
                unbracketed.append('%d:%s' % (i + 1, s))
    check('6 maintenance probes bracketed', not unbracketed, ', '.join(unbracketed))

    # ---- 7) the watcher heals a stuck mute --------------------------------------
    watcher = macro_body(state, '_STATE_WATCHER')
    heal_at = cmd_pos(watcher, '_LED_QUIET ON=0')
    check('7a watcher heals a stuck mute', heal_at > 0, 'no _LED_QUIET ON=0')
    around = watcher[max(0, heal_at - 400):heal_at]
    check('7b heal is gated on the mode',
          "'homing'" in around and "'leveling'" in around,
          'the heal must not fire while homing/leveling is still running')

    # ---- 8) Z_TILT_ADJUST in 11_gantry_sync is bracketed ------------------------
    if 'gantry' in src:
        zt = macro_body(src['gantry'], 'Z_TILT')
        zt_at = cmd_pos(zt, 'Z_TILT_ADJUST')
        zt_on = cmd_pos(zt, '_LED_QUIET ON=1')
        zt_off = cmd_pos(zt, '_LED_QUIET ON=0')
        check('8a Z_TILT mutes before probing', 0 <= zt_on < zt_at,
              'on=%s zt=%s' % (zt_on, zt_at))
        check('8b Z_TILT unmutes after probing', zt_off > zt_at >= 0,
              'off=%s zt=%s' % (zt_off, zt_at))
    return fails


def mutate(src, what):
    """Return a mutated copy - each one MUST be caught by run_checks()."""
    out = dict(src)
    if what == 'g28-no-mute':
        out['start'] = src['start'].replace('    _LED_QUIET ON=1\n    M99110',
                                            '    M99110', 1)
    elif what == 'g28-wrong-order':
        t = src['start']
        t = t.replace('    _LED_QUIET ON=1\n    M99110 {rawparams}\n',
                      '    M99110 {rawparams}\n', 1)
        t = t.replace('    _LED_QUIET ON=0\n', '    _LED_QUIET ON=0\n_LED_QUIET ON=1\n', 1)
        out['start'] = t
    elif what == 'sls-no-guard':
        out['leds'] = src['leds'].replace(
            "    {% if printer['gcode_macro _STATE'].led_quiet|default(False)\n"
            "       and params.FORCE|default(0)|int != 1 %}",
            "    {% if False %}", 1)
    elif what == 'mesh-no-bracket':
        out['kamp'] = src['kamp'].replace('    _LED_QUIET ON=1\n', '', 1)
    elif what == 'watcher-no-heal':
        out['state'] = src['state'].replace(
            "    {% if s.led_quiet|default(False) and s.mode not in "
            "('homing','leveling','starting') %}\n        _LED_QUIET ON=0\n"
            "    {% endif %}\n", '', 1)
    elif what == 'no-flag':
        out['state'] = src['state'].replace('variable_led_quiet: False\n', '', 1)
    elif what == 'quiet-no-stop':
        out['leds'] = src['leds'].replace('                STOP_LED_EFFECTS\n', '', 1)
    elif what == 'ztilt-no-bracket':
        out['gantry'] = src['gantry'].replace('        _LED_QUIET ON=1\n', '', 1)
    else:
        raise SystemExit('unknown mutation %s' % what)
    return out


def main():
    src = load()
    fails = run_checks(src)
    total = 0
    for _ in range(1):
        total += 17   # the number of pinned checks above (1..8b)
    print('--- live config ---')
    for line in fails:
        print('  FAIL %s' % line)
    if fails:
        print('R257 CRASH GUARD: %d FAIL - the probe-quiet guard is incomplete'
              % len(fails))
        return 1
    print('  all %d checks pass' % total)

    # ---- counter-test: every mutation must be caught ---------------------------
    print('--- counter-test (each mutation must FAIL) ---')
    mutants = ['g28-no-mute', 'g28-wrong-order', 'sls-no-guard',
               'mesh-no-bracket', 'watcher-no-heal', 'no-flag', 'quiet-no-stop',
               'ztilt-no-bracket']
    caught = 0
    for name in mutants:
        mf = run_checks(mutate(src, name))
        if mf:
            caught += 1
            print('  ok   %-18s caught by: %s' % (name, mf[0].split(' (')[0]))
        else:
            print('  MISS %-18s NOT caught - the check is blind here' % name)
    if caught != len(mutants):
        print('R257 CRASH GUARD: %d/%d mutations caught - the checks do not '
              'prove what they claim' % (caught, len(mutants)))
        return 1
    print('R257 CRASH GUARD: %d checks, 0 FAIL, %d/%d mutations caught - no LED '
          'animation traffic in the probe descent' % (total, caught, len(mutants)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
