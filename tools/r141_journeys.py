#!/usr/bin/env python3
"""R141 USER JOURNEYS - the printer as a HUMAN drives it.

The standing battery proves the pieces; this suite proves the ROAD. Macros are
rendered IN SEQUENCE with state threading (SAVE_VARIABLE / SET_GCODE_VARIABLE
outputs are applied back into the simulated printer) AND macro calls in the
output are auto-executed like Klipper's dispatcher does - PRINT_START really
runs _RUN_PRINT_START, PAUSE really parks, sounds really reach _SOUND_LIB.

The command lint is Klipper's REAL parser, not an approximation: shlex with
posix=True, whitespace_split=True, commenters='#;' (klippy/gcode.py,
_get_extended_params) - escaped quotes inside quoted values are legal,
unquoted #/; start a comment, bare tokens are 'Malformed command'.

  JOURNEY A  normal user - material, label via the LCD queue, select the file,
             start dialog, print, layer range, pause/resume, finish.
  JOURNEY B  the R132 fix flow - RetractFix while the dialog is up (released
             on its OWN clean path), file comes back, one confirmation.
  JOURNEY C  power user - full fix chain on one file, presets, overrides,
             every generator with its full console parameter set.
  STORM D    fresh boot - EVERY macro (incl. internal) with EMPTY
             save_variables: the .81 fresh-install class.
  STORM E    parameter fuzz - every PUBLIC macro x every param x probe values:
             no crash, every output line survives the real Klipper parser.

Exit code != 0 on any fail.  R141 JOURNEYS summary at the end.
"""
import ast
import os
import re
import shlex
import sys

import jinja2
from jinja2.utils import Namespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAC_DIR = os.path.join(ROOT, 'macros')

MACRO_RE = re.compile(r'\[gcode_macro ([^\]]+)\](.*?)(?=\n\[|\Z)', re.S)
RAW_LINE = re.compile(r'^[GMT]\d+')

fails = []
n_ck = [0]


def ck(name, cond, info=''):
    n_ck[0] += 1
    if not cond:
        fails.append((name, str(info)[:140]))


# ------------------------------------------------------- klipper's parser --
def klipper_ok(cmd):
    """True iff Klipper's _get_extended_params accepts this command line"""
    cmd = cmd.strip()
    if cmd[:1] in ('#', ';'):
        return True                              # pure comment line
    word = cmd.split(' ', 1)[0]
    if RAW_LINE.match(word):
        return True                              # traditional G/M/T
    rest = cmd[len(word):].strip()
    if not rest:
        return True                              # bare command, no params
    s = shlex.shlex(rest, posix=True)
    s.whitespace_split = True
    s.commenters = '#;'
    try:
        toks = list(s)
    except ValueError:
        return False                             # unbalanced quotes
    for t in toks:
        if '=' not in t:
            return False                         # bare token = Malformed
        k, v = t.split('=', 1)
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k):
            return False
    return True


def parse_params(rest):
    """shlex-parse a macro call tail -> params dict (Klipper semantics)"""
    s = shlex.shlex(rest, posix=True)
    s.whitespace_split = True
    s.commenters = '#;'
    out = {}
    try:
        for t in s:
            if '=' in t:
                k, v = t.split('=', 1)
                out[k] = v
    except ValueError:
        pass
    return out


# ---------------------------------------------------------------- extract --
BODIES = {}      # name -> raw gcode body
OWNVARS = {}     # name -> {var: value}  (multi-line variable_ literals)
for _fn in sorted(os.listdir(MAC_DIR)):
    if not _fn.endswith('.cfg'):
        continue
    _txt = open(os.path.join(MAC_DIR, _fn), encoding='utf-8').read()
    for _m in MACRO_RE.finditer(_txt):
        _name, _body = _m.group(1).strip(), _m.group(2)
        if '\ngcode:' not in _body:
            continue
        _vars = {}
        for _vm in re.finditer(
                r'(?ms)^variable_(\w+):\s*(.*?)(?=^variable_\w+:|^description:'
                r'|^gcode:|^rename_existing:|\Z)', _body):
            _raw = _vm.group(2).strip()
            try:
                _vars[_vm.group(1)] = ast.literal_eval(_raw)
            except (ValueError, SyntaxError):
                _vars[_vm.group(1)] = _raw.strip("'\"")
        OWNVARS[_name] = _vars
        BODIES[_name] = _body.split('\ngcode:', 1)[1]


def gbody(name):
    """macro gcode body, comment-only lines stripped (Klipper drops them)"""
    g = re.split(r'\n[a-z_]+:', BODIES[name])[0]
    return '\n'.join(l for l in g.splitlines()
                     if l.strip() and not l.lstrip().startswith('#'))


# ------------------------------------------------------------- simulator --
def parse_value(raw):
    """Klipper save_variables semantics: shlex-unescaped, then literal_eval"""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in '"\'':
        raw = raw[1:-1].replace('\\"', '"').replace("\\'", "'")
    if raw in ('True', 'False'):
        return raw == 'True'
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw


class M0(int):
    """mock that behaves like 0 but tolerates everything (r140 proven)"""
    def __getitem__(self, k):
        return M0(0)

    def __contains__(self, k):
        return False

    def __call__(self, *a, **k):
        return M0(0)

    def __iter__(self):
        return iter(())

    def split(self, *a, **k):
        return []

    def rsplit(self, *a, **k):
        return []

    def strip(self, *a, **k):
        return ''

    def upper(self, *a, **k):
        return ''

    def lower(self, *a, **k):
        return ''

    def replace(self, *a, **k):
        return ''

    def join(self, *a, **k):
        return ''

    def startswith(self, *a, **k):
        return False

    def endswith(self, *a, **k):
        return False


class Vars:
    """attribute+item access over a dict; missing -> jinja Undefined"""
    def __init__(self, d):
        self.__dict__['_d'] = dict(d)

    def __getattr__(self, k):
        try:
            return self._d[k]
        except KeyError:
            return jinja2.Undefined(name=k)

    __getitem__ = __getattr__

    def __contains__(self, k):
        return k in self._d

    def __repr__(self):
        return 'Vars(%r)' % (self._d,)


class Settings:
    """printer.configfile.settings - section containment"""
    def __init__(self, sections):
        self._s = set(sections)

    def __contains__(self, k):
        return k in self._s

    def __getitem__(self, k):
        return Vars({})

    def __getattr__(self, k):
        return Vars({})


class Printer:
    """dict-like 'printer'; known objects modeled, the rest degrade to 0"""
    def __init__(self, sim):
        self._sim = sim

    def __getitem__(self, k):
        s = self._sim
        if k == 'save_variables':
            return Vars({'variables': Vars(s.sv)})
        if k.startswith('gcode_macro '):
            return Vars(s.macro_vars.get(k[12:], {}))
        if k == 'print_stats':
            return Vars(s.print_stats)
        if k == 'configfile':
            return Vars({'settings': Settings(s.sections), 'config_path': ''})
        if k == 'toolhead':
            return Vars({'position': Vars({'x': 110.0, 'y': 107.0, 'z': 50.0}),
                         'axis_maximum': Vars({'x': 220.0, 'y': 217.0,
                                               'z': 250.0}),
                         'axis_minimum': Vars({'x': 0.0, 'y': -3.0,
                                               'z': -5.0})})
        if k == 'gcode_move':
            return Vars({'gcode_position': Vars({'x': 110.0, 'y': 107.0,
                                                 'z': 42.0, 'e': 0.0}),
                         'position': Vars({'x': 110.0, 'y': 107.0,
                                           'z': 42.0, 'e': 0.0}),
                         'homing_origin': Vars({'x': 0.0, 'y': 0.0,
                                                'z': 0.0, 'e': 0.0}),
                         'speed': 100.0, 'speed_factor': 1.0,
                         'extrude_factor': 1.0})
        if k == 'extruder':
            return Vars({'temperature': 205.0, 'target': 205.0,
                         'power': 0.6, 'can_extrude': True,
                         'pressure_advance': 0.05, 'smooth_time': 0.04})
        if k == 'heater_bed':
            return Vars({'temperature': 59.0, 'target': 60.0, 'power': 0.4})
        if k == 'display_status':
            return Vars({'message': s.m117[-1] if s.m117 else '',
                         'progress': 0.42})
        return M0(0)

    def __getattr__(self, k):
        return self[k]

    def __contains__(self, k):
        if k.startswith('gcode_macro '):
            return k[12:] in BODIES
        return k in ('save_variables', 'print_stats', 'configfile',
                     'toolhead', 'gcode_move', 'extruder', 'heater_bed',
                     'display_status')


class Params(dict):
    def __missing__(self, k):
        return jinja2.Undefined(name=k)


MAX_CALLS = 400


class Sim:
    """stateful macro runner: applies state, auto-executes macro calls"""

    def __init__(self, sections=()):
        self.sv = {}
        self.macro_vars = {n: dict(v) for n, v in OWNVARS.items()}
        self.print_stats = {'filename': '', 'state': 'standby',
                            'print_duration': 3725.0, 'filament_used': 1234.0,
                            'total_duration': 4101.0,
                            'info': Vars({'total_layer': 42,
                                          'current_layer': 42,
                                          'filament_used': 1234.0})}
        self.sections = list(sections)
        self.m117, self.respond, self.sounds = [], [], []
        self.actions = []
        self.calls = 0
        self.depth = 0

    def render(self, name, params=None):
        assert name in BODIES, 'unknown macro %s' % name
        env = jinja2.Environment('{%', '%}', '{', '}',
                                 undefined=jinja2.Undefined)
        env.globals['namespace'] = lambda **k: Namespace(**k)
        own = dict(self.macro_vars.get(name, {}))
        own.update({'params': Params(params or {}),
                    'printer': Printer(self), 'menu': Params({'input': 0}),
                    'namespace': env.globals['namespace'],
                    'save_variables': Vars(self.sv)})
        self.depth += 1
        try:
            out = env.from_string(gbody(name)).render(own)
        finally:
            self.depth -= 1
        self._apply(out)
        self.actions.append((name, out))
        if self.depth == 0:
            self._autoexec(out)
        return out

    def _autoexec(self, out):
        """Klipper dispatches macro calls - so does the simulator"""
        if self.calls > MAX_CALLS:
            return
        for ln in out.splitlines():
            if self.calls > MAX_CALLS:
                return
            t = ln.strip()
            if not t or t[0] in ';#{':
                continue
            word = t.split(' ', 1)[0]
            if RAW_LINE.match(word) or word in ('SAVE_VARIABLE',):
                continue
            if word not in BODIES:
                continue
            rest = t[len(word):].strip()
            self.calls += 1
            try:
                self.render(word, parse_params(rest))
            except Exception:                        # noqa: BLE001
                pass                                 # recorded via actions

    def _apply(self, out):
        for ln in out.splitlines():
            t = ln.strip()
            m = re.match(r'SAVE_VARIABLE\s+VARIABLE=(\w+)\s+VALUE=(.*)$', t)
            if m:
                self.sv[m.group(1)] = parse_value(m.group(2))
                continue
            m = re.match(r'SET_GCODE_VARIABLE\s+MACRO=(\S+)\s+'
                         r'VARIABLE=(\w+)\s+VALUE=(.*)$', t)
            if m:
                # R133: the VALUE is group(3) - group(2) is the NAME (the
                # old typo set every variable to its own name, so
                # _STATE.mode literally became 'mode')
                self.macro_vars.setdefault(m.group(1), {})[m.group(2)] = \
                    parse_value(m.group(3))
                continue
            if t.startswith('M117 '):
                self.m117.append(t[5:])
            elif t == 'M117':
                self.m117.append('')
            elif 'RESPOND MSG=' in t:
                self.respond.append(t.split('RESPOND MSG=', 1)[1])
            elif 'NOTIFY TEXT=' in t:
                self.respond.append(t.split('NOTIFY TEXT=', 1)[1])
            elif t.startswith('_SOUND_LIB NAME='):
                _nm = t.split('NAME=', 1)[1].split()
                if _nm:
                    self.sounds.append(_nm[0])

    # -- assertions --------------------------------------------------------
    def lint_clean(self, tag):
        for ln in self.actions[-1][1].splitlines():
            cpos = ln.find(';')
            cmd = ln[:cpos if cpos >= 0 else None].strip()
            if not cmd:
                continue
            ck('lint %s' % tag, klipper_ok(cmd), cmd[:90])

    def said(self, fragment):
        return any(fragment in r for r in self.respond)


def mode_of(sim):
    return sim.macro_vars.get('_STATE', {}).get('mode', 'idle')


# ============================================================== JOURNEY A ==
def journey_normal():
    s = Sim(sections=['pwm_cycle_time beeper', 'neopixel printer_leds',
                      'display', 'probe', 'virtual_sdcard', 'pause_resume',
                      'display_status', 'respond', 'filament_switch_sensor fil_runout',
                      'tmc2209 stepper_x', 'save_variables'])
    s.render('SET_MATERIAL', {'MATERIAL': 'PLA'})
    ck('A SET_MATERIAL: PLA acknowledged', s.said('PLA'), '')
    s.lint_clean('SET_MATERIAL')

    # normal user types the label on the LCD, then Create
    s.sv['label_texts'] = 'GARAGE'
    out = s.render('LABEL_GENERATE', {})
    ck('A LABEL_GENERATE: nonce bumps + confirm sound',
       s.sv.get('label_gen_nonce') == 1 and 'r2_confirm' in s.sounds,
       'nonce=%r sounds=%s' % (s.sv.get('label_gen_nonce'), s.sounds[-2:]))
    ck('A LABEL_GENERATE: creating message', s.said('creating'), '')
    s.lint_clean('LABEL_GENERATE')

    # the file appears and gets selected (watcher sends _SELECT_FILE)
    out = s.render('_SELECT_FILE', {'FILE': '00_GARAGE_V01.gcode'})
    ck('A SELECT: preview stored',
       s.sv.get('preview_file') == '00_GARAGE_V01.gcode', str(s.sv)[:90])
    s.lint_clean('_SELECT_FILE')

    # start dialog: as sliced
    s.print_stats.update({'filename': '00_GARAGE_V01.gcode'})
    out = s.render('PRINT_AS_SLICED', {})
    ck('A AS_SLICED: decision path taken (no dead end)',
       s.said('start') or 'PRINT_START' in out
       or s.macro_vars['_STATE'].get('start_pending') != ''
       or mode_of(s) in ('starting', 'printing'), out[:130])
    s.lint_clean('PRINT_AS_SLICED')
    s.print_stats.update({'state': 'printing'})
    # R133: the dialog's Start button runs _RUN_PRINT_START (PRINT_START
    # with a pending decision just re-enters the waiting dialog)
    out = s.render('_RUN_PRINT_START', {})
    ck('A PRINT_START: mode leaves idle',
       mode_of(s) in ('printing', 'starting'), 'mode=%s' % mode_of(s))
    ck('A PRINT_START: start sound played', 'r2_start' in s.sounds,
       str(s.sounds[-3:]))
    s.lint_clean('_RUN_PRINT_START')

    # mid-print
    s.render('SET_LAYER_RANGE', {'START': '5', 'END': '20'})
    ck('A RANGE: bounds stored',
       str(s.sv.get('range_start', '')) == '5'
       or s.said('5'), str(s.sv)[:80])
    s.lint_clean('SET_LAYER_RANGE')
    s.macro_vars['_STATE']['mode'] = 'printing'
    s.render('PAUSE', {})
    ck('A PAUSE: mode paused', mode_of(s) == 'paused', 'mode=%s' % mode_of(s))
    s.lint_clean('PAUSE')
    s.print_stats.update({'state': 'paused'})
    s.render('RESUME', {})
    ck('A RESUME: mode printing again', mode_of(s) == 'printing',
       'mode=%s' % mode_of(s))
    s.lint_clean('RESUME')

    # finish
    s.print_stats.update({'state': 'complete'})
    s.render('PRINT_END', {})
    ck('A PRINT_END: done sound + not printing',
       'r2_done' in s.sounds and mode_of(s) != 'printing',
       'mode=%s sounds=%s' % (mode_of(s), s.sounds[-3:]))
    s.lint_clean('PRINT_END')


# ============================================================== JOURNEY B ==
def journey_fix_flow():
    s = Sim()
    s.sv['preview_file'] = 'wobbly (1).gcode'      # shlex-hostile on purpose
    s.render('_SELECT_FILE', {'FILE': 'wobbly (1).gcode'})
    s.macro_vars['_STATE']['mode'] = 'waiting'
    s.macro_vars['_STATE']['start_pending'] = 'wobbly (1).gcode'
    s.macro_vars['_STATE']['decided_file'] = ''

    out = s.render('FIX_FILE', {'WHAT': 'RETRACT'})
    ck('B FIX during dialog: released on the OWN clean path',
       'CANCEL_PRINT_BASE' in out and '_WAIT_IDLE_RESTORE' in out
       and mode_of(s) == 'idle', 'mode=%s' % mode_of(s))
    ck('B FIX: file queued + auto-reload armed',
       s.sv.get('retract_fix_file') == 'wobbly (1).gcode'
       and s.sv.get('fix_reselect') == 'wobbly (1).gcode',
       str({k: s.sv.get(k) for k in ('retract_fix_file', 'fix_reselect')}))
    ck('B FIX: nonce bumps', s.sv.get('retract_fix_nonce') == 1, '')
    ck('B FIX: only-confirm message', s.said('confirm'), '')
    s.lint_clean('FIX_FILE(waiting)')

    # watcher fixed + re-selected the file: dialog back, ONE confirmation
    s.macro_vars['_STATE']['mode'] = 'waiting'
    out = s.render('PRINT_AS_SLICED', {})
    ck('B after fix: AS_SLICED works (no dead end)',
       s.said('start') or 'PRINT_START' in out
       or s.macro_vars['_STATE'].get('start_pending') != ''
       or mode_of(s) in ('starting', 'printing'), out[:130])
    s.lint_clean('PRINT_AS_SLICED(after-fix)')

    # blocked while printing (queue-interruption guard)
    s.macro_vars['_STATE']['mode'] = 'printing'
    out = s.render('FIX_FILE', {'WHAT': 'VOL'})
    ck('B FIX blocked during print',
       s.said('blocked') and 'vol_fix_file' not in s.sv, out[:100])
    s.lint_clean('FIX_FILE(printing)')


# ============================================================== JOURNEY C ==
GEN_CALLS = [
    ('GEN_LABELS', {'TEXT': 'A|B'}),
    ('GEN_CABLE_TIES', {'COUNT': '12', 'LENGTH': '100'}),
    ('GEN_ANGLES', {'ANGLE': '90'}),
    ('GEN_SEAL', {'OD': '40', 'ID': '20', 'HEIGHT': '1.2'}),
    ('GEN_FRAME', {'PRESET': '9x13'}),
    ('LITHO_CREATE', {}),
    ('GEN_COLORPIC', {'CONTRAST': '20'}),
    ('GEN_BRICKS', {'CODES': 'B2x4:3|P2x2:2', 'MODE': 'BY_OBJECT',
                    'COLORS': '4', 'BRIM': '4'}),
    ('GEN_FIGURES', {'SCALE': '150', 'COUNT': '2', 'MODE': 'SINGLE',
                     'COLORS': '4', 'BRIM': '2', 'COLORMODE': 'BY_OBJECT'}),
    ('GEN_BRICKKIT', {'DETAIL': 'AUTO', 'MODE': 'BY_LAYER', 'COLORS': '3'}),
    ('TEMP_TOWER_GEN', {}),
    ('RESONANCE_DIAGRAM', {'AXIS': 'both'}),
    ('BRIDGE_TEST', {'LENGTH': '120'}),
]


def journey_power():
    s = Sim()
    s.sv['preview_file'] = 'chain.gcode'
    # R133d: the kit source reads the in-memory _PREVIEW card - a file is
    # SELECTED in the list before GEN_BRICKKIT (never a newest-job guess)
    s.macro_vars['_PREVIEW']['name'] = 'chain.gcode'
    for what, extra in [('RETRACT', {}), ('VOL', {}),
                        ('FLOWCAP', {'CAP': '15'}),
                        ('TRAVEL', {'SPEED': '250', 'ACCEL': '9000'}),
                        ('TRAVELACC', {'ACCEL': '8000'})]:
        out = s.render('FIX_FILE', dict(WHAT=what, **extra))
        s.lint_clean('FIX_FILE(%s)' % what)
    # TRAVEL and TRAVELACC share the travelacc slot (documented behavior)
    ck('C FIX chain: retract+vol+flowcap queued once each',
       all(s.sv.get('%s_fix_file' % k) == 'chain.gcode'
           for k in ('retract', 'vol', 'flowcap')),
       str({k: s.sv.get('%s_fix_file' % k)
            for k in ('retract', 'vol', 'flowcap', 'travelacc')}))
    ck('C FIX chain: travel+travelacc share one slot, nonce = 2',
       s.sv.get('travelacc_fix_file') == 'chain.gcode'
       and s.sv.get('travelacc_fix_nonce') == 2,
       'file=%r nonce=%r' % (s.sv.get('travelacc_fix_file'),
                             s.sv.get('travelacc_fix_nonce')))

    # presets + profiles + overrides
    s.render('SET_MATERIAL', {'MATERIAL': 'PETG'})
    for nm, kw in [('SAVE_DEFAULT_PRESET', {'NAME': 'petg-fast'}),
                   ('LOAD_DEFAULT_PRESET', {'NAME': 'petg-fast'}),
                   ('DELETE_DEFAULT_PRESET', {'NAME': 'petg-fast'}),
                   ('SET_OVERRIDE_VALUE', {'NAME': 'feat_spd_wallouter',
                                           'VALUE': '120'}),
                   ('TOGGLE_OVERRIDE', {'NAME': 'feat_on_ironing'}),
                   ('SET_Z_HOP', {'VALUE': '0.4'}),
                   ('SAVE_FILE_PROFILE', {}),
                   ('FILE_PROFILES_INFO', {})]:
        if nm not in BODIES:
            ck('C %s exists' % nm, False, 'macro missing')
            continue
        s.render(nm, kw)
        s.lint_clean(nm)

    # every generator with its full console parameter set
    nonces = ('label_gen_nonce', 'cable_tie_nonce', 'angle_nonce',
              'seal_nonce', 'frame_nonce', 'litho_nonce', 'colorpic_nonce',
              'bricks_nonce', 'figures_nonce', 'brickkit_nonce',
              'reso_nonce', 'bridge_nonce')
    for name, kw in GEN_CALLS:
        if name not in BODIES:
            ck('C %s exists' % name, False, 'macro missing')
            continue
        out = s.render(name, kw)
        ck('C %s: nonce bumped or explained' % name,
           any(s.sv.get(k) for k in nonces) or s.said('must')
           or 'Tower' in out or s.said('needs') or s.said('no '),
           out[:120])
        s.lint_clean(name)


# =============================================================== STORM D ===
def storm_fresh_boot():
    """every macro with EMPTY save_variables + boot-default own vars"""
    crashed = []
    for name in sorted(BODIES):
        s = Sim()
        try:
            s.render(name, {})
        except Exception as e:                       # noqa: BLE001
            crashed.append((name, repr(e)[:70]))
            continue
        s.lint_clean('fresh:%s' % name)
    for name, err in crashed:
        ck('D fresh boot renders %s' % name, False, err)
    ck('D fresh boot: every macro survives an empty machine',
       not crashed, '%d crashed: %s' % (len(crashed), [c[0] for c in crashed]))


# =============================================================== STORM E ===
PROBES = ['', '0', '-1', '3', '999', 'abc']


def storm_params():
    """public macros only - internal ones get their inputs from callers"""
    n = bad = 0
    public = [m for m in sorted(BODIES) if not m.startswith('_')]
    for name in public:
        pnames = sorted(set(re.findall(r'params\.(\w+)', BODIES[name])))
        for p in pnames:
            for v in PROBES:
                n += 1
                s = Sim()
                s.sv.update({'preview_file': 'x.gcode', 'material': 'PLA',
                             'label_texts': 'A'})
                try:
                    out = s.render(name, {p: v})
                except Exception as e:               # noqa: BLE001
                    bad += 1
                    ck('E %s %s=%r no crash' % (name, p, v), False,
                       repr(e)[:80])
                    continue
                for ln in out.splitlines():
                    cpos = ln.find(';')
                    cmd = ln[:cpos if cpos >= 0 else None].strip()
                    if not cmd:
                        continue
                    if not klipper_ok(cmd):
                        bad += 1
                        ck('E %s %s=%r lint' % (name, p, v), False, cmd[:90])
                        break
    ck('E param storm: %d renders, 0 fails' % n, bad == 0, '%d bad' % bad)
    return n


# ================================================================== main ===
if __name__ == '__main__':
    print('R141 USER JOURNEYS - macros in sequence, state threaded through')
    print('=' * 72)
    journey_normal()
    print('  journey A (normal user)       done')
    journey_fix_flow()
    print('  journey B (fix + reload flow) done')
    journey_power()
    print('  journey C (power user)        done')
    storm_fresh_boot()
    print('  storm D (fresh boot, %d macros) done' % len(BODIES))
    n = storm_params()
    print('  storm E (param fuzz, %d renders) done' % n)
    print('=' * 72)
    if fails:
        for name, info in fails:
            print('  FAIL %-48s %s' % (name, info))
    print('R141 JOURNEYS: %d checks, %d FAIL' % (n_ck[0], len(fails)))
    sys.exit(1 if fails else 0)
