#!/usr/bin/env python3
"""Read-only, offline G-code state trace prototype. Not a postprocessor.

Outputs JSON Lines to stdout; it never executes commands or writes the input.
Numbers are *G-code coordinate values*, not measured machine position. Unknown
commands conservatively invalidate tracked coordinates. Only explicitly handled
syntax is interpreted. This is not wired to a watcher or printer.
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
# Non-motion commands whose effects on this limited coordinate model are known.
PASSIVE = {'M104': 'ST', 'M109': 'ST', 'M140': 'S', 'M190': 'S',
           'M106': 'SP', 'M107': 'P', 'M204': 'PST', 'M220': 'S',
           'M221': 'S', 'M400': '', 'G4': 'PS'}


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


class Shadow:
    def __init__(self, assume_klipper_defaults=False, dialect='klipper', assumed_passive=()):
        if dialect not in ('klipper', 'generic'):
            raise ValueError('unsupported dialect')
        self.assumed_passive = frozenset(name.upper() for name in assumed_passive)
        core = {'G0', 'G1', 'G90', 'G91', 'G92', 'G20', 'G21', 'M82', 'M83'}
        if any(not re.fullmatch(r'[A-Z_][A-Z0-9_]*', n) or n in core
               or (re.match(r'[GMT]\d', n) and not re.fullmatch(r'[GMT]\d+', n))
               for n in self.assumed_passive):
            raise ValueError('invalid passive assumption or core command')
        self.dialect = dialect
        # A file may start after arbitrary start macros. Defaults are opt-in.
        self.xyz_absolute = True if assume_klipper_defaults else None
        self.e_absolute = True if assume_klipper_defaults else None
        self.units_mm = 1.0 if assume_klipper_defaults else None
        self.position = {axis: None for axis in AXES}
        self.e = None
        self.feed_mm_min = None
        self.tool = 0

    def invalidate(self):
        self.position = {axis: None for axis in AXES}
        self.e = None
        self.feed_mm_min = None
        self.xyz_absolute = None
        self.e_absolute = None
        self.units_mm = None

    def process(self, raw, line_number):
        """One record per raw line. All state is local, no commands executed."""
        code, _, comment = raw.rstrip('\r\n').partition(';')
        rec = {'line': line_number, 'raw': raw, 'comment': comment if ';' in raw else None,
               'kind': 'comment' if not code.strip() else 'unknown'}
        if not code.strip():
            return rec
        # Explicit, user-provided assumptions are never inferred from names.
        # They describe a hypothetical trace, not the installed macro or proof
        # that a command can neither move nor change modes.
        token = code.strip().split(None, 1)[0].upper()
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
        try:
            params = parameters(code[match.end():])
        except ValueError as exc:
            self.invalidate()
            rec['reason'] = str(exc) + '; coordinate state invalidated'
            return rec
        rec['parameters'] = params
        if command in ('G90', 'G91', 'M82', 'M83', 'G20', 'G21') and not params:
            if command == 'G20' and self.dialect == 'klipper':
                self.invalidate()
                rec['reason'] = 'Klipper rejects G20; execution would stop; state invalidated'
                return rec
            if command == 'G90': self.xyz_absolute = True
            elif command == 'G91': self.xyz_absolute = False
            elif command == 'M82': self.e_absolute = True
            elif command == 'M83': self.e_absolute = False
            elif command == 'G20': self.units_mm = 25.4
            else: self.units_mm = 1.0
            rec['kind'] = 'mode'
            return rec
        if command.startswith('T') and '.' not in command and not params:
            self.tool = int(command[1:])
            self.invalidate()  # a Klipper tool macro may change positions and modes
            rec.update(kind='tool', tool=self.tool,
                       reason='tool macro effects unknown; coordinate and modal state invalidated')
            return rec
        if command == 'G92' and params and set(params) <= set(AXES + ('E',)):
            if self.units_mm is None or any(not math.isfinite(v * self.units_mm) for v in params.values()):
                self.invalidate()
                rec['reason'] = 'unknown units or numeric overflow; state invalidated'
                return rec
            for axis in AXES:
                if axis in params: self.position[axis] = params[axis] * self.units_mm
            if 'E' in params: self.e = params['E'] * self.units_mm
            rec.update(kind='coordinate_reset', position_mm=self.position.copy(), e_mm=self.e,
                       reason='logical G-code coordinates; physical origin not inferred')
            return rec
        if command in ('G0', 'G1') and set(params) <= set(AXES + ('E', 'F')):
            effective_e_absolute = self.e_absolute
            if self.dialect == 'klipper' and self.e_absolute is True:
                # In Klipper G91 makes E relative even if M82 is selected.
                effective_e_absolute = self.xyz_absolute
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
            rec.update(kind='move', start_mm=start, end_mm=end,
                       commanded_e_delta_mm=delta_e, feed_mm_min=feed,
                       tool=self.tool, xyz_mode=('absolute' if self.xyz_absolute is True else
                                                'relative' if self.xyz_absolute is False else 'unknown'),
                       e_mode=('absolute' if effective_e_absolute is True else
                               'relative' if effective_e_absolute is False else 'unknown'),
                       dialect=self.dialect,
                       note='commanded filament delta only; flow and physical position not inferred')
            return rec
        if command in PASSIVE and set(params) <= set(PASSIVE[command]):
            rec['kind'] = 'non_motion_event'
            return rec
        # Arcs, homing, macros, retraction and unrecognised commands can alter
        # positions or modes. Require explicit modes before interpreting moves.
        self.invalidate()
        rec['reason'] = 'unsupported command; coordinate and modal state invalidated'
        return rec


def trace(path, assume_klipper_defaults=False, dialect='klipper', assumed_passive=()):
    state = Shadow(assume_klipper_defaults=assume_klipper_defaults, dialect=dialect,
                   assumed_passive=assumed_passive)
    with Path(path).open('r', encoding='utf-8', errors='surrogateescape', newline='') as source:
        for number, line in enumerate(source, 1):
            yield state.process(line, number)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='existing G-code file, opened for reading only')
    parser.add_argument('--assume-klipper-defaults', action='store_true',
                        help='assume G21/G90/M82 at entry; not proof of machine state')
    parser.add_argument('--dialect', choices=('klipper', 'generic'), default='klipper',
                        help='generic assumes independent XYZ/E modes and supports G20')
    parser.add_argument('--assume-passive', action='append', default=[], metavar='COMMAND',
                        help='assume command does not alter tracked state (hypothetical, repeatable)')
    args = parser.parse_args()
    try:
        for record in trace(args.input, assume_klipper_defaults=args.assume_klipper_defaults,
                            dialect=args.dialect, assumed_passive=args.assume_passive):
            print(json.dumps(record, ensure_ascii=True, separators=(',', ':')))
    except (OSError, ValueError, BrokenPipeError) as exc:
        print('shadow: %s' % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
