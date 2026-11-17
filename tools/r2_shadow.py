#!/usr/bin/env python3
"""Read-only, offline G-code state trace engine. Not a postprocessor.

Outputs JSON Lines to stdout; it never executes commands or writes the input.
Numbers are *G-code coordinate values*, not measured machine position. Unknown
commands conservatively invalidate tracked coordinates. Optional capabilities
(`enable_arcs`, `firmware_retract`, `klipper_passive`, `verified_r2_passive`,
`assume_klipper_defaults`) are strictly opt-in and explicitly recorded so
traces never hide assumptions.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

COMMAND = re.compile(r'^\s*([GMT]\d+(?:\.\d+)?)(?=$|\s|[A-Za-z])', re.I)
PARAM = re.compile(r'\s*([A-Za-z])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))')
AXES = ('X', 'Y', 'Z')

# Non-motion G/M commands whose lack of effect on logical coordinates/modes is known.
PASSIVE = {
    'M73': 'PRCSQD',
    'M104': 'ST', 'M105': '', 'M106': 'SP', 'M107': 'P', 'M108': '',
    'M109': 'ST', 'M114': '', 'M115': '',
    'M140': 'S', 'M141': 'S', 'M190': 'S', 'M191': 'S',
    'M201': 'XYZE', 'M203': 'XYZE', 'M204': 'PSTR', 'M205': 'XYZEJSTBQ',
    'M220': 'S', 'M221': 'S', 'M400': '', 'M572': 'DS', 'M900': 'KLST',
    'G4': 'PS',
}

# Non-motion extended Klipper/slicer commands (only honored when klipper_passive=True).
KLIPPER_PASSIVE_COMMANDS = frozenset({
    'M117', 'M118', 'RESPOND', 'SET_DISPLAY_TEXT',
    'EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT_START', 'EXCLUDE_OBJECT_END',
    'SET_PRESSURE_ADVANCE', 'SET_VELOCITY_LIMIT',
    'SET_FAN_SPEED', 'M106', 'TIMELAPSE_TAKE_FRAME',
    'SET_PRINT_STATS_INFO', 'CLEAR_PAUSE',
})

# R2 post-processor metadata/feature markers whose macro bodies in macros/ do
# not move axes or alter G90/G91/M82/M83/G92 state (opt-in via verified_r2_passive=True).
VERIFIED_R2_PASSIVE_COMMANDS = frozenset({
    '_FILE_INFO', 'LAYER_MARK', 'APPLY_TYPE',
})

CORE_COMMANDS = frozenset({
    'G0', 'G1', 'G2', 'G3', 'G17', 'G18', 'G19',
    'G20', 'G21', 'G28', 'G90', 'G91', 'G92',
    'M18', 'M82', 'M83', 'M84',
})


def parameters(text):
    """Parse compact/space-separated single-letter numeric parameters strictly."""
    params = {}
    pos = 0
    while pos < len(text):
        if not text[pos:].strip():
            break
        match = PARAM.match(text, pos)
        if match is None:
            raise ValueError('unsupported parameter syntax')
        key, value = match.group(1).upper(), float(match.group(2))
        if key in params or not math.isfinite(value):
            raise ValueError('duplicate or non-finite parameter')
        params[key] = value
        pos = match.end()
    return params


def _arc_geometry_xy(sx, sy, ex, ey, i_off, j_off, clockwise):
    """Validate and compute exact G17 XY arc geometry (Klipper gcode_arcs model).

    Returns (cx, cy, radius_mm, sweep_rad, arc_length_mm, bounds_xy_mm) or raises
    ValueError if the arc is degenerate, inconsistent, or non-finite.
    """
    cx = sx + i_off
    cy = sy + j_off
    if not (math.isfinite(cx) and math.isfinite(cy)):
        raise ValueError('non-finite arc center')
    r0 = math.hypot(sx - cx, sy - cy)
    r1 = math.hypot(ex - cx, ey - cy)
    if not (math.isfinite(r0) and math.isfinite(r1)) or r0 < 1e-4 or r1 < 1e-4:
        raise ValueError('degenerate zero-radius arc')
    # Reject inconsistent center-to-start vs center-to-end radii (fail closed).
    tol = max(0.05, 0.01 * max(r0, r1))
    if abs(r0 - r1) > tol:
        raise ValueError('inconsistent arc radius (start %.4f vs end %.4f mm)' % (r0, r1))
    a0 = math.atan2(sy - cy, sx - cx)
    full_circle = math.hypot(ex - sx, ey - sy) <= 1e-6
    if full_circle:
        sweep = -2.0 * math.pi if clockwise else 2.0 * math.pi
    else:
        a1 = math.atan2(ey - cy, ex - cx)
        if clockwise:
            sweep = a1 - a0
            if sweep >= -1e-12:
                sweep -= 2.0 * math.pi
        else:
            sweep = a1 - a0
            if sweep <= 1e-12:
                sweep += 2.0 * math.pi
    r_avg = 0.5 * (r0 + r1)
    arc_len = r_avg * abs(sweep)
    if not math.isfinite(arc_len):
        raise ValueError('numeric overflow in arc length')

    # Exact XY bounding box including any cardinal extrema crossed by the sweep.
    xs = [sx, ex]
    ys = [sy, ey]
    for card_ang, px, py in (
        (0.0, cx + r_avg, cy),
        (0.5 * math.pi, cx, cy + r_avg),
        (math.pi, cx - r_avg, cy),
        (-0.5 * math.pi, cx, cy - r_avg),
    ):
        if full_circle:
            xs.append(px)
            ys.append(py)
            continue
        if clockwise:
            diff = (a0 - card_ang) % (2.0 * math.pi)
            if 0.0 <= diff <= abs(sweep) + 1e-12:
                xs.append(px)
                ys.append(py)
        else:
            diff = (card_ang - a0) % (2.0 * math.pi)
            if 0.0 <= diff <= sweep + 1e-12:
                xs.append(px)
                ys.append(py)
    bounds = [min(xs), min(ys), max(xs), max(ys)]
    return cx, cy, r_avg, sweep, arc_len, bounds


def sample_arc_points(record, resolution_mm=1.0):
    """Subdivide an `arc` record into [(x, y, z), ...] polyline points (start..end)."""
    res = max(0.1, float(resolution_mm))
    start, end = record['start_mm'], record['end_mm']
    cx, cy = record['center_mm']['X'], record['center_mm']['Y']
    sx, sy, sz = start['X'], start['Y'], start['Z']
    ex, ey, ez = end['X'], end['Y'], end['Z']
    sweep = record['sweep_rad']
    arc_len = record['arc_length_mm']
    r0 = math.hypot(sx - cx, sy - cy)
    r1 = math.hypot(ex - cx, ey - cy)
    a0 = math.atan2(sy - cy, sx - cx)
    steps = max(1, min(4096, int(math.ceil(arc_len / res))))
    pts = [(sx, sy, sz)]
    for k in range(1, steps):
        t = k / float(steps)
        ang = a0 + sweep * t
        rk = r0 + (r1 - r0) * t
        zk = (sz + (ez - sz) * t) if (sz is not None and ez is not None) else ez
        pts.append((cx + rk * math.cos(ang), cy + rk * math.sin(ang), zk))
    pts.append((ex, ey, ez))
    return pts


class Shadow:
    def __init__(self, assume_klipper_defaults=False, dialect='klipper',
                 assumed_passive=(), *, enable_arcs=False,
                 firmware_retract=False, klipper_passive=False,
                 verified_r2_passive=False):
        if dialect not in ('klipper', 'generic'):
            raise ValueError('unsupported dialect')
        self.assumed_passive = frozenset(name.upper() for name in assumed_passive)
        if any(not re.fullmatch(r'[A-Z_][A-Z0-9_]*', n) or n in CORE_COMMANDS
               or (re.match(r'[GMT]\d', n) and not re.fullmatch(r'[GMT]\d+', n))
               for n in self.assumed_passive):
            raise ValueError('invalid passive assumption or core command')
        self.dialect = dialect
        self.enable_arcs = bool(enable_arcs)
        self.firmware_retract = bool(firmware_retract)
        self.klipper_passive = bool(klipper_passive)
        self.verified_r2_passive = bool(verified_r2_passive)
        # A file may start after arbitrary start macros. Defaults are opt-in.
        self.xyz_absolute = True if assume_klipper_defaults else None
        self.e_absolute = True if assume_klipper_defaults else None
        self.units_mm = 1.0 if assume_klipper_defaults else None
        self.arc_plane = 'XY' if (assume_klipper_defaults and self.enable_arcs) else None
        self.position = {axis: None for axis in AXES}
        self.e = None
        self.feed_mm_min = None
        self.fw_retracted = False if self.firmware_retract else None
        self.tool = 0

    def options_summary(self):
        return {
            'dialect': self.dialect,
            'enable_arcs': self.enable_arcs,
            'firmware_retract': self.firmware_retract,
            'klipper_passive': self.klipper_passive,
            'verified_r2_passive': self.verified_r2_passive,
            'assumed_passive': sorted(self.assumed_passive),
        }

    def invalidate(self):
        self.position = {axis: None for axis in AXES}
        self.e = None
        self.feed_mm_min = None
        self.xyz_absolute = None
        self.e_absolute = None
        self.units_mm = None
        self.arc_plane = None
        if self.firmware_retract:
            self.fw_retracted = None

    def invalidate_axes(self, axes=AXES):
        """Invalidate physical/logical coordinates of unhomed/disabled axes."""
        for ax in axes:
            if ax in self.position:
                self.position[ax] = None

    def _effective_e_absolute(self):
        eff = self.e_absolute
        if self.dialect == 'klipper' and self.e_absolute is True:
            # In Klipper G91 forces E relative even when M82 is selected.
            eff = self.xyz_absolute
        return eff

    def process(self, raw, line_number):
        """One record per raw line. All state is local, no commands executed."""
        code, _, comment = raw.rstrip('\r\n').partition(';')
        rec = {'line': line_number, 'raw': raw,
               'comment': comment if ';' in raw else None,
               'kind': 'comment' if not code.strip() else 'unknown'}
        if not code.strip():
            return rec
        token = code.strip().split(None, 1)[0].upper()
        # Verified R2 metadata/type markers (opt-in) and Klipper non-motion commands
        # (opt-in) carry distinct provenance from unverified user assumptions.
        if self.verified_r2_passive and token in VERIFIED_R2_PASSIVE_COMMANDS:
            rec.update(kind='verified_r2_passive', command=token,
                       reason='opt-in R2 passive marker; no axis or modal change modelled')
            return rec
        if self.klipper_passive and token in KLIPPER_PASSIVE_COMMANDS and token != 'M106':
            rec.update(kind='klipper_passive', command=token,
                       reason='opt-in non-motion Klipper command; no axis or modal change modelled')
            return rec
        if token in self.assumed_passive:
            rec.update(kind='assumed_passive', command=token,
                       reason='user assumption: effects on tracked state ignored; not verified')
            return rec
        match = COMMAND.match(code)
        if not match:
            self.invalidate()
            rec['reason'] = 'unsupported command syntax; coordinate state invalidated'
            return rec
        command = match.group(1).upper()
        rec['command'] = command
        rest = code[match.end():]
        # M84 / M18 accept bare axis flags (e.g. `M84 X Y`, `M84`, `M84 S0`, `M84 X0 E0`).
        if command in ('M84', 'M18'):
            flag_axes = []
            ok_m84 = True
            for tok in rest.strip().split():
                tu = tok.upper()
                if tu in ('X', 'Y', 'Z', 'E'):
                    if tu in flag_axes:
                        ok_m84 = False
                        break
                    flag_axes.append(tu)
                elif re.fullmatch(r'[XYZES][+-]?(?:\d+(?:\.\d*)?|\.\d+)', tu):
                    k_ax = tu[0]
                    fv = float(tu[1:])
                    if not math.isfinite(fv) or k_ax in flag_axes:
                        ok_m84 = False
                        break
                    flag_axes.append(k_ax)
                else:
                    ok_m84 = False
                    break
            if not ok_m84:
                self.invalidate()
                rec['reason'] = 'unsupported parameter syntax; coordinate state invalidated'
                return rec
            specified = tuple(ax for ax in AXES if ax in flag_axes)
            only_e = ('E' in flag_axes and not specified and 'S' not in flag_axes)
            disabled = () if only_e else (specified if specified else AXES)
            self.invalidate_axes(disabled)
            if 'E' in flag_axes or not specified:
                self.e = None
            rec.update(kind='motors_off', disabled_axes=list(disabled),
                       position_mm=self.position.copy(),
                       reason='motors disabled; disabled axis and extruder coordinates invalidated')
            return rec
        try:
            params = parameters(rest)
        except ValueError as exc:
            self.invalidate()
            rec['reason'] = str(exc) + '; coordinate state invalidated'
            return rec
        rec['parameters'] = params

        # Modal positioning / unit commands
        if command in ('G90', 'G91', 'M82', 'M83', 'G20', 'G21') and not params:
            if command == 'G20' and self.dialect == 'klipper':
                self.invalidate()
                rec['reason'] = 'Klipper rejects G20; execution would stop; state invalidated'
                return rec
            if command == 'G90':
                self.xyz_absolute = True
            elif command == 'G91':
                self.xyz_absolute = False
            elif command == 'M82':
                self.e_absolute = True
            elif command == 'M83':
                self.e_absolute = False
            elif command == 'G20':
                self.units_mm = 25.4
            else:
                self.units_mm = 1.0
            rec['kind'] = 'mode'
            return rec

        # Arc plane selection (G17 XY supported when enable_arcs=True; G18/G19 fail closed)
        if command in ('G17', 'G18', 'G19') and not params:
            if not self.enable_arcs:
                self.invalidate()
                rec['reason'] = 'arc plane command requires enable_arcs; state invalidated'
                return rec
            if command == 'G17':
                self.arc_plane = 'XY'
                rec.update(kind='mode', arc_plane='XY')
                return rec
            self.invalidate()
            rec['reason'] = f'unsupported arc plane {command} (only G17 XY supported); state invalidated'
            return rec

        # Opt-in firmware retraction G10 / G11 (Klipper [firmware_retraction])
        if self.firmware_retract and command in ('G10', 'G11') and not params:
            self.fw_retracted = (command == 'G10')
            rec.update(kind='firmware_retract', retracted=self.fw_retracted,
                       reason='opt-in Klipper firmware_retraction; G-code XYZ/E coordinates unchanged')
            return rec

        # Tool change
        if command.startswith('T') and '.' not in command and not params:
            self.tool = int(command[1:])
            self.invalidate()  # a Klipper tool macro may change positions and modes
            rec.update(kind='tool', tool=self.tool,
                       reason='tool macro effects unknown; coordinate and modal state invalidated')
            return rec

        # Coordinate reset G92
        if command == 'G92' and params and set(params) <= set(AXES + ('E',)):
            if self.units_mm is None or any(not math.isfinite(v * self.units_mm) for v in params.values()):
                self.invalidate()
                rec['reason'] = 'unknown units or numeric overflow; state invalidated'
                return rec
            for axis in AXES:
                if axis in params:
                    self.position[axis] = params[axis] * self.units_mm
            if 'E' in params:
                self.e = params['E'] * self.units_mm
            rec.update(kind='coordinate_reset', position_mm=self.position.copy(), e_mm=self.e,
                       reason='logical G-code coordinates; physical origin not inferred')
            return rec

        # Linear move G0 / G1
        if command in ('G0', 'G1') and set(params) <= set(AXES + ('E', 'F')):
            effective_e_absolute = self._effective_e_absolute()
            if (self.units_mm is None
                    or (any(axis in params for axis in AXES) and self.xyz_absolute is None)
                    or ('E' in params and effective_e_absolute is None)
                    or ('F' in params and params['F'] <= 0)):
                self.invalidate()
                rec['reason'] = 'unknown units/mode or invalid feed; state invalidated'
                return rec
            start = self.position.copy()
            end = start.copy()
            for axis in AXES:
                if axis in params:
                    value = params[axis] * self.units_mm
                    end[axis] = value if self.xyz_absolute else (
                        None if start[axis] is None else start[axis] + value)
            delta_e, new_e = 0.0, self.e
            if 'E' in params:
                value = params['E'] * self.units_mm
                if effective_e_absolute:
                    delta_e = None if self.e is None else value - self.e
                    new_e = value
                else:
                    delta_e = value
                    new_e = None if self.e is None else self.e + value
            feed = params['F'] * self.units_mm if 'F' in params else self.feed_mm_min
            if any(v is not None and not math.isfinite(v)
                   for v in (*end.values(), delta_e, new_e, feed)):
                self.invalidate()
                rec['reason'] = 'numeric overflow; state invalidated'
                return rec
            self.position, self.e, self.feed_mm_min = end, new_e, feed
            rec.update(
                kind='move', start_mm=start, end_mm=end,
                commanded_e_delta_mm=delta_e, feed_mm_min=feed,
                tool=self.tool,
                xyz_mode=('absolute' if self.xyz_absolute is True else
                          'relative' if self.xyz_absolute is False else 'unknown'),
                e_mode=('absolute' if effective_e_absolute is True else
                        'relative' if effective_e_absolute is False else 'unknown'),
                dialect=self.dialect,
                note='commanded filament delta only; flow and physical position not inferred')
            return rec

        # Planar/helical XY arc G2 (CW) / G3 (CCW) — opt-in, G17 XY I/J only, fail-closed
        if command in ('G2', 'G3'):
            if not self.enable_arcs:
                self.invalidate()
                rec['reason'] = 'unsupported command; coordinate and modal state invalidated'
                return rec
            allowed = set(AXES + ('I', 'J', 'E', 'F'))
            effective_e_absolute = self._effective_e_absolute()
            plane = self.arc_plane or ('XY' if self.units_mm is not None else None)
            if (not set(params) <= allowed
                    or ('I' not in params and 'J' not in params)
                    or plane != 'XY'
                    or self.units_mm is None
                    or self.xyz_absolute is None
                    or self.position['X'] is None or self.position['Y'] is None
                    or ('Z' in params and not self.xyz_absolute and self.position['Z'] is None)
                    or ('E' in params and effective_e_absolute is None)
                    or ('F' in params and params['F'] <= 0)):
                self.invalidate()
                rec['reason'] = 'unsupported or incomplete arc parameters/state; state invalidated'
                return rec
            start = self.position.copy()
            end = start.copy()
            for axis in AXES:
                if axis in params:
                    value = params[axis] * self.units_mm
                    end[axis] = value if self.xyz_absolute else (start[axis] + value)
            i_off = params.get('I', 0.0) * self.units_mm
            j_off = params.get('J', 0.0) * self.units_mm
            clockwise = (command == 'G2')
            try:
                cx, cy, radius_mm, sweep_rad, arc_len, bounds_xy = _arc_geometry_xy(
                    start['X'], start['Y'], end['X'], end['Y'],
                    i_off, j_off, clockwise)
            except ValueError as exc:
                self.invalidate()
                rec['reason'] = str(exc) + '; state invalidated'
                return rec
            dz = 0.0
            if start['Z'] is not None and end['Z'] is not None:
                dz = end['Z'] - start['Z']
            path_len_3d = math.hypot(arc_len, dz)
            delta_e, new_e = 0.0, self.e
            if 'E' in params:
                value = params['E'] * self.units_mm
                if effective_e_absolute:
                    delta_e = None if self.e is None else value - self.e
                    new_e = value
                else:
                    delta_e = value
                    new_e = None if self.e is None else self.e + value
            feed = params['F'] * self.units_mm if 'F' in params else self.feed_mm_min
            if any(v is not None and not math.isfinite(v)
                   for v in (*end.values(), cx, cy, radius_mm, sweep_rad,
                             arc_len, path_len_3d, delta_e, new_e, feed)):
                self.invalidate()
                rec['reason'] = 'numeric overflow in arc; state invalidated'
                return rec
            self.position, self.e, self.feed_mm_min = end, new_e, feed
            self.arc_plane = 'XY'
            rec.update(
                kind='arc', plane='XY', clockwise=clockwise,
                start_mm=start, end_mm=end,
                center_mm={'X': cx, 'Y': cy},
                radius_mm=radius_mm, sweep_rad=sweep_rad,
                arc_length_mm=arc_len, path_length_3d_mm=path_len_3d,
                bounds_xy_mm=bounds_xy,
                commanded_e_delta_mm=delta_e, feed_mm_min=feed,
                tool=self.tool,
                xyz_mode='absolute' if self.xyz_absolute else 'relative',
                e_mode=('absolute' if effective_e_absolute is True else
                        'relative' if effective_e_absolute is False else 'unknown'),
                dialect=self.dialect,
                note='opt-in G17 XY I/J arc model; requires [gcode_arcs] in Klipper')
            return rec

        if command in PASSIVE and set(params) <= set(PASSIVE[command]):
            rec['kind'] = 'non_motion_event'
            return rec

        # Homing, unrecognised macros, R-form arcs, G90.1/G91.1 fail closed.
        self.invalidate()
        rec['reason'] = 'unsupported command; coordinate and modal state invalidated'
        return rec


def trace(path, assume_klipper_defaults=False, dialect='klipper',
          assumed_passive=(), *, enable_arcs=False, firmware_retract=False,
          klipper_passive=False, verified_r2_passive=False):
    state = Shadow(
        assume_klipper_defaults=assume_klipper_defaults,
        dialect=dialect,
        assumed_passive=assumed_passive,
        enable_arcs=enable_arcs,
        firmware_retract=firmware_retract,
        klipper_passive=klipper_passive,
        verified_r2_passive=verified_r2_passive,
    )
    with Path(path).open('r', encoding='utf-8', errors='surrogateescape', newline='') as source:
        for number, line in enumerate(source, 1):
            yield state.process(line, number)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='existing G-code file, opened for reading only')
    parser.add_argument('--assume-klipper-defaults', action='store_true',
                        help='assume G21/G90/M82 at entry; not proof of machine state')
    parser.add_argument('--dialect', choices=('klipper', 'generic'), default='klipper',
                        help='generic assumes independent XYZ/E modes and supports G20')
    parser.add_argument('--enable-arcs', action='store_true',
                        help='interpret G17 XY I/J G2/G3 arcs (requires [gcode_arcs]); fail closed on G18/G19/R')
    parser.add_argument('--firmware-retract', action='store_true',
                        help='model G10/G11 as Klipper firmware retraction without invalidating coordinates')
    parser.add_argument('--klipper-passive', action='store_true',
                        help='treat known non-motion Klipper commands (EXCLUDE_OBJECT_*, M117, RESPOND, SET_PRESSURE_ADVANCE, SET_VELOCITY_LIMIT) as passive')
    parser.add_argument('--verified-r2-passive', action='store_true',
                        help='treat R2 metadata/type markers (_FILE_INFO, LAYER_MARK, APPLY_TYPE) as passive')
    parser.add_argument('--assume-passive', action='append', default=[], metavar='COMMAND',
                        help='assume command does not alter tracked state (hypothetical, repeatable)')
    args = parser.parse_args(argv)
    try:
        for record in trace(
            args.input,
            assume_klipper_defaults=args.assume_klipper_defaults,
            dialect=args.dialect,
            assumed_passive=args.assume_passive,
            enable_arcs=args.enable_arcs,
            firmware_retract=args.firmware_retract,
            klipper_passive=args.klipper_passive,
            verified_r2_passive=args.verified_r2_passive,
        ):
            print(json.dumps(record, ensure_ascii=True, separators=(',', ':')))
    except (OSError, ValueError, BrokenPipeError) as exc:
        print('shadow: %s' % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
