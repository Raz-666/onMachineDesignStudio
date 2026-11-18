#!/usr/bin/env python3
# ============================================================================
# toolchain.py — Toolchain-Preset-Vertrag (Gesamtbriefing §20/§22.4), Phase 1
# ============================================================================
# WAS DAS IST (und was NICHT):
#   Experimenteller, offline nutzbarer Vertrag fuer Toolchain-Presets: eine
#   geordnete Folge von Pre-Print-Werkzeugjobs (§20.1), validiert gegen eine
#   kleine, quellenbelegte Tool-Registry, plus ein reiner PLAN (Eingabe/
#   Ausgabe/Temp-Verlauf je Schritt) OHNE irgendeine Ausfuehrung.
#
#   §20.2: Ein Preset enthaelt NIEMALS eine fest verdrahtete Eingabedatei —
#   beim Laden wird es auf die aktuell ausgewaehlte Datei angewendet.
#   validate_preset() lehnt entsprechende Schluessel ab.
#
#   §20.3/§22.4: Job N+1 startet erst nach validierter Ausgabe von Job N;
#   Zwischenstaende sind temporaer, bis der Nachfolger sie uebernommen hat.
#   Der Plan markiert genau das (temp-Flag + requires-Gate je Schritt).
#
#   §20.5 (drei Ebenen): Tools = TOOL_REGISTRY, Toolchains = plan_chain(),
#   Toolchain-Presets = das JSON-Dokument, das validate_preset() prueft.
#
# REGISTRY-PROVENIENZ (alles gegen den Code belegt, nicht aus Doku geraten):
#   range   — tools/r2_postproc.py:1937 make_range(src, start, end, floor,
#             top, brim, ...): Schichtfenster, Ausgabe <stem>_L<s>-<e>.gcode
#   scale   — menus/lcd_menues.cfg:3883 ff. __preprint __mods __scale:
#             X/Y 25..300 %, Top X/Y 0..300 % (Flow wird mitgerechnet)
#   texture — macros/17_generator.cfg:1178-1180 (27 Muster-Codes),
#             LCD-Wertebereiche menus/lcd_menues.cfg:3361 ff.
#             (Around 3..80 mm, Height 0.5..200 mm, Depth 0.05..1.0 mm)
#   Multi-Output-Werkzeuge (Cake: PART=BOTH -> zwei Dateien) sind in Ketten
#   NOCH NICHT zugelassen (outputs != 1 wird abgelehnt): die Verzweigungs-
#   semantik ist in §20 nicht spezifiziert und wird hier nicht erfunden.
#
# GRENZEN (bewusst, Phase 1):
#   - kein Ausfuehren, kein Queue-/Watcher-/Makro-Anschluss
#   - Registry mit 3 verankerten Werkzeugen; Phase 2 extrahiert die
#     vollstaendige Werkzeugliste aus den Menue-Daten (menu_json_export.py)
#   - Ausgabe-Namenskonvention Vnn_<stem>.gcode im Ordner Toolchain/ ist ein
#     VORSCHLAG (analog zum Cake/-Ordner), noch kein Systemverhalten
# ============================================================================

import argparse
import json
import re
import sys

SCHEMA = 'r2-toolchain/1'
PLAN_SCHEMA = 'r2-toolchain-plan/1'
MAX_STEPS = 16
MAX_PARAMS_PER_STEP = 16
MAX_DESCRIPTION = 200

# §20.2 — Presets enthalten keine Eingabedatei. Diese Schluessel (in jeder
# Ebene: Preset, Step, Params) werden kategorisch abgelehnt.
_FORBIDDEN_KEYS = re.compile(
    r'^(input|infile|in_file|file|source|src|path|filename|gcode_file)$', re.I)

_PRESET_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _().+-]{0,63}$')
_INPUT_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _().+-]*\.gcode$')

# macros/17_generator.cfg:1179 — die 27 Muster-Codes (Reihenfolge dort).
TEXTURE_PATTERNS = (
    'RIDGES', 'WAVES', 'GRID', 'HATCH', 'CHECKER', 'HEX', 'HONEYCOMB',
    'BASKET', 'ROPE', 'PLANKS', 'BRICKS', 'SANDSTONE', 'CONCRETE', 'CLAY',
    'CREPE', 'FABRIC', 'PLUSH', 'HILBERT', 'SCRATCH', 'GLITCH', 'KNIT',
    'FLUTED', 'BARK', 'SCALES', 'FACETS', 'MACRAME', 'MAP',
)

TOOL_REGISTRY = {
    'range': {
        'title': 'Range — Schichtfenster (r2_postproc.make_range:1937)',
        'outputs': 1,
        'params': {
            'start': {'type': 'int', 'min': 1, 'max': 9999, 'required': True},
            'end': {'type': 'int', 'min': 1, 'max': 9999, 'required': True},
            'floor': {'type': 'int', 'min': 0, 'max': 50,
                      'required': False, 'default': 0},
            'top': {'type': 'int', 'min': 0, 'max': 50,
                    'required': False, 'default': 0},
            'brim': {'type': 'int', 'min': 0, 'max': 20,
                     'required': False, 'default': 0},
        },
        # Querschnittsregel: Fenster muss nicht-leer und nicht invertiert sein.
        'rules': [{'a': 'start', 'b': 'end', 'op': 'le'}],
    },
    'scale': {
        'title': 'Scale — X/Y/Taper (menus/lcd_menues.cfg:3883 ff.)',
        'outputs': 1,
        'params': {
            'x': {'type': 'int', 'min': 25, 'max': 300, 'required': True},
            'y': {'type': 'int', 'min': 25, 'max': 300, 'required': True},
            'top_x': {'type': 'int', 'min': 0, 'max': 300,
                      'required': False, 'default': 0},
            'top_y': {'type': 'int', 'min': 0, 'max': 300,
                      'required': False, 'default': 0},
        },
        'rules': [],
    },
    'texture': {
        'title': 'Texture — Muster auf Aussenwand (17_generator.cfg:1178 ff.)',
        'outputs': 1,
        'params': {
            'pattern': {'type': 'enum', 'values': TEXTURE_PATTERNS,
                        'required': True},
            'scale_mm': {'type': 'number', 'min': 3.0, 'max': 80.0,
                         'required': True},
            'zsize_mm': {'type': 'number', 'min': 0.5, 'max': 200.0,
                         'required': True},
            'depth_mm': {'type': 'number', 'min': 0.05, 'max': 1.0,
                         'required': True},
            'direction': {'type': 'enum', 'values': ('IN', 'OUT'),
                          'required': False, 'default': 'OUT'},
            'seed': {'type': 'int', 'min': 0, 'max': 999999,
                     'required': False, 'default': 1},
        },
        'rules': [],
    },
}


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _type_ok(value, spec):
    kind = spec['type']
    if kind == 'int':
        return _is_int(value)
    if kind == 'number':
        return _is_number(value)
    if kind == 'enum':
        return isinstance(value, str) and value in spec['values']
    return False


def _check_forbidden(mapping, where, errors):
    for key in mapping:
        if _FORBIDDEN_KEYS.match(str(key)):
            errors.append(
                '%s: Schluessel "%s" ist verboten — Presets enthalten keine '
                'Eingabedatei (Gesamtbriefing §20.2)' % (where, key))


def _validate_params(tool, params, where, errors):
    if not isinstance(params, dict):
        errors.append('%s: "params" muss ein Objekt sein' % where)
        return
    _check_forbidden(params, where + '.params', errors)
    spec = TOOL_REGISTRY[tool]['params']
    if len(params) > MAX_PARAMS_PER_STEP:
        errors.append('%s: zu viele Parameter (%d > %d)'
                      % (where, len(params), MAX_PARAMS_PER_STEP))
    for name, value in params.items():
        if name not in spec:
            errors.append('%s: Werkzeug "%s" kennt Parameter "%s" nicht '
                          '(erlaubt: %s)'
                          % (where, tool, name, ', '.join(sorted(spec))))
            continue
        pspec = spec[name]
        if not _type_ok(value, pspec):
            errors.append('%s: Parameter "%s" hat falschen Typ (%s erwartet)'
                          % (where, name, pspec['type']))
            continue
        if 'min' in pspec and value < pspec['min']:
            errors.append('%s: Parameter "%s" = %r unter Minimum %r'
                          % (where, name, value, pspec['min']))
        if 'max' in pspec and value > pspec['max']:
            errors.append('%s: Parameter "%s" = %r ueber Maximum %r'
                          % (where, name, value, pspec['max']))
    for name, pspec in spec.items():
        if pspec.get('required') and name not in params:
            errors.append('%s: Pflichtparameter "%s" fehlt (Werkzeug "%s")'
                          % (where, name, tool))
    # Querschnittsregeln (nur wenn beide Felder sauber vorhanden sind).
    for rule in TOOL_REGISTRY[tool].get('rules', ()):
        a = params.get(rule['a'])
        b = params.get(rule['b'])
        if _is_number(a) and _is_number(b):
            if rule['op'] == 'le' and not a <= b:
                errors.append('%s: "%s" (%r) muss <= "%s" (%r) sein'
                              % (where, rule['a'], a, rule['b'], b))


def validate_preset(preset):
    """Prueft ein Toolchain-Preset gegen den Vertrag.

    Rueckgabe: (ok_bool, errors_liste) — Fehler sind Klartext mit
    Schritt-Bezug, niemals eine Ausnahme. Keine Datei wird angefasst.
    """
    errors = []
    if not isinstance(preset, dict):
        return False, ['Preset muss ein JSON-Objekt sein']
    _check_forbidden(preset, 'preset', errors)

    allowed_top = {'schema', 'name', 'description', 'steps'}
    for key in preset:
        if key not in allowed_top:
            errors.append('preset: unbekannter Schluessel "%s" (erlaubt: %s)'
                          % (key, ', '.join(sorted(allowed_top))))

    if preset.get('schema') != SCHEMA:
        errors.append('preset: "schema" muss "%s" sein' % SCHEMA)
    name = preset.get('name')
    if not isinstance(name, str) or not _PRESET_NAME_RE.match(name):
        errors.append('preset: "name" fehlt oder ist ungueltig '
                      '(1-64 Zeichen, kein Pfadtrenner)')
    description = preset.get('description')
    if description is not None:
        if not isinstance(description, str):
            errors.append('preset: "description" muss ein String sein')
        elif len(description) > MAX_DESCRIPTION:
            errors.append('preset: "description" zu lang (%d > %d)'
                          % (len(description), MAX_DESCRIPTION))

    steps = preset.get('steps')
    if not isinstance(steps, list) or not steps:
        errors.append('preset: "steps" fehlt oder ist leer')
        return False, errors
    if len(steps) > MAX_STEPS:
        errors.append('preset: %d Schritte uebersteigen das Maximum %d'
                      % (len(steps), MAX_STEPS))

    for idx, step in enumerate(steps, start=1):
        where = 'Schritt %d' % idx
        if not isinstance(step, dict):
            errors.append('%s: muss ein Objekt sein' % where)
            continue
        _check_forbidden(step, where, errors)
        for key in step:
            if key not in ('tool', 'params'):
                errors.append('%s: unbekannter Schluessel "%s"' % (where, key))
        tool = step.get('tool')
        if tool not in TOOL_REGISTRY:
            errors.append('%s: unbekanntes Werkzeug %r (registriert: %s)'
                          % (where, tool, ', '.join(sorted(TOOL_REGISTRY))))
            continue
        if TOOL_REGISTRY[tool].get('outputs', 1) != 1:
            errors.append('%s: Werkzeug "%s" erzeugt mehrere Ausgaben — '
                          'in Ketten (noch) nicht zulaessig' % (where, tool))
        if 'params' in step:
            _validate_params(tool, step['params'], where, errors)
        else:
            errors.append('%s: "params" fehlt' % where)

    return not errors, errors


def _effective_params(tool, params):
    spec = TOOL_REGISTRY[tool]['params']
    merged = dict(params or {})
    for name, pspec in spec.items():
        if name not in merged and 'default' in pspec:
            merged[name] = pspec['default']
    return merged


def plan_chain(preset, input_name):
    """Baut den reinen Ausfuehrungsplan: welche Jobs, in welcher Reihenfolge,

    mit welcher Ein-/Ausgabe-Datei und welchem Temp-/Gate-Status. Fuehrt
    NICHTS aus und schreibt keine Datei — der Plan ist der Praefezierungs-
    stand fuer Phase 2 (Ausfuehrung im Job-Service mit Validierungs-Gates).
    """
    ok, errors = validate_preset(preset)
    if not ok:
        return None, errors
    if not isinstance(input_name, str) or not _INPUT_NAME_RE.match(input_name):
        return None, ['Eingabedatei %r ist kein plain .gcode-Dateiname '
                      '(keine Pfade — §20.2: die Auswahl trifft der Nutzer '
                      'zur Laufzeit)' % input_name]

    stem = input_name[:-len('.gcode')]
    steps = []
    current_input = input_name
    for idx, step in enumerate(preset['steps'], start=1):
        tool = step['tool']
        output = 'V%02d_%s.gcode' % (idx, stem)
        job = {
            'job': idx,
            'tool': tool,
            'title': TOOL_REGISTRY[tool]['title'],
            'params': _effective_params(tool, step.get('params')),
            'input': current_input,
            'output': output,
            # §20.3/§22.4: Zwischenstand, bis der Nachfolger ihn uebernommen
            # hat; nur die letzte Ausgabe ist dauerhaft.
            'temp': idx < len(preset['steps']),
        }
        if idx > 1:
            job['requires'] = 'validierte Ausgabe von Job %d' % (idx - 1)
        steps.append(job)
        current_input = output

    plan = {
        'schema': PLAN_SCHEMA,
        'input': input_name,
        'output_dir': 'Toolchain/',   # VORSCHLAG analog Cake/, kein Ist-Stand
        'naming': 'V<nn>_<stem>.gcode (Vorschlag, Versionierungs-Konvention '
                  'wie Cake/Range)',
        'steps': steps,
        'final_output': steps[-1]['output'],
        'temp_outputs': sum(1 for s in steps if s['temp']),
        'limits': [
            'Plan ohne Ausfuehrung — Phase 1 des Toolchain-Konzepts '
            '(analyse/TOOLCHAIN-KONZEPT.md)',
            'Job N+1 startet erst nach validierter Ausgabe von Job N '
            '(§20.3/§22.4) — Durchsetzung folgt in Phase 2',
            'Temporaere Zwischenstaende werden erst geloescht, wenn der '
            'Naechste sie uebernommen hat (§22.4)',
            'Original bleibt unveraendert (§20.2)',
        ],
    }
    return plan, []


def registry_report():
    """Kurzbericht ueber die Registry (fuer Tests und spaetige UI-Anzeige)."""
    report = {}
    for tool, spec in TOOL_REGISTRY.items():
        report[tool] = {
            'title': spec['title'],
            'outputs': spec.get('outputs', 1),
            'params': sorted(spec['params']),
            'required': sorted(p for p, v in spec['params'].items()
                               if v.get('required')),
        }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Toolchain-Preset validieren und planen (Phase 1, '
                    'keine Ausfuehrung)')
    parser.add_argument('preset', help='Pfad zur Preset-JSON-Datei')
    parser.add_argument('--input', default=None,
                        help='ausgewaehlte .gcode-Datei (nur fuer den Plan; '
                             'gehört NIEMALS ins Preset selbst, §20.2)')
    args = parser.parse_args(argv)

    with open(args.preset, 'r', encoding='utf-8') as handle:
        preset = json.load(handle)

    ok, errors = validate_preset(preset)
    result = {'schema': SCHEMA, 'ok': ok, 'errors': errors}
    if ok and args.input:
        plan, plan_errors = plan_chain(preset, args.input)
        result['plan'] = plan
        result['errors'].extend(plan_errors)
        result['ok'] = plan is not None
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write('\n')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
