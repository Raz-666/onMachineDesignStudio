#!/usr/bin/env python3
# ============================================================================
# toolchain.py — Toolchain-Vertrag + Ausführungs-Engine (§20/§21/§22), Phase 1+2a
# ============================================================================
# WAS DAS IST (und was NICHT):
#   Experimenteller, offline nutzbarer Vertrag fuer Toolchain-Presets UND
#   eine Ausfuehrungs-Engine mit den Gates aus dem Gesamtbriefing:
#     - §20.1  geordnete Kette: jedes Werkzeug erhaelt die Ausgabe des
#              vorherigen (plan_chain + run_chain)
#     - §20.2  Presets enthalten NIEMALS eine Eingabedatei (erzwungen)
#     - §20.3/§22.4 Job N+1 erst nach validierter Ausgabe von Job N;
#              temporäre Zwischenstände werden erst gelöscht, wenn der
#              Nachfolger sie übernommen hat (Engine setzt genau das um)
#     - §21    Ausgabemodi save/preview/queue für die Gesamtkette
#     - §22.1  Zustände queued/running/success/failed/cancelled; Erfolg
#              heisst: Datei existiert, lesbar, nicht leer, registriert
#
# REGISTRY — ZWEI SICHTEN, EINE WAHRHEIT:
#   TOOL_REGISTRY  : handverifizierte Anker (range/scale/texture) mit
#                    semantischen Parameternamen — Grundlage des
#                    Preset-Vertrags. Alle Bereiche sind GEGEN das LCD-
#                    Menü gesichert (registry_drift() == leer, CI-Test).
#   build_registry(): vollständige Werkzeugliste AUS DEN MENÜ-DATEN
#                    (web/menu_structure.json, exportiert von
#                    menu_json_export.py — Quelle der Wahrheit): 8 Mods-
#                    Werkzeuge mit ihren LCD-Wertebereichen. Ändert jemand
#                    das Menü, schlägt der Drift-Test an.
#
# PROVENIENZ (Code, nicht Doku):
#   range   — tools/r2_postproc.py:1937 make_range(src, start, end, floor,
#             top, brim, first_h, floor_shape, floor_fill, top_shape,
#             top_fill, floor_hole, top_hole, ...)
#   scale   — menus/lcd_menues.cfg:3883 ff. (X/Y 25..300 %, Top 0..300 %)
#   texture — macros/17_generator.cfg:1178-1180 (27 Muster-Codes),
#             Richtung: lcd_menues.cfg:3458 (LCD-Index 1 = OUT, 0 = IN),
#             Engine-Default 'OUT' (r2_postproc.py:28286)
#   Menü    — web/menu_structure.json, Baum __main __preprint __mods mit
#             input_min/input_max/input_step und SAVE_VARIABLE-Namen
#
# GRENZEN (bewusst, Phase 2a):
#   - run_chain arbeitet mit EINSETZBAREN Schritt-Funktionen (step_runner);
#     die ANBINDUNG der echten System-Werkzeuge (Watcher/_spawn_job/Makros)
#     ist Phase 2b — hier wird NICHTS am Produkt r2_postproc.py geändert
#   - Multi-Output-Werkzeuge (Cake PART=BOTH -> U+L) bleiben in Ketten
#     abgelehnt (outputs != 1), bis die Verzweigungssemantik geklärt ist
#   - Ausgabe-Namenskonvention Vnn_<stem>.gcode im Ordner Toolchain/ ist
#     SEIT R259 (Phase 2b/2) Systemverhalten: der Watcher hebt die Nummer
#     mit _next_gen_version an (plan_chain, first_version) — kein zweiter
#     Lauf kollidiert mit der Endausgabe des ersten.
# ============================================================================

import argparse
import json
import os
import re
import sys
import time

SCHEMA = 'r2-toolchain/1'
PLAN_SCHEMA = 'r2-toolchain-plan/1'
RUN_SCHEMA = 'r2-toolchain-run/1'
MAX_STEPS = 16
MAX_PARAMS_PER_STEP = 16
MAX_DESCRIPTION = 200
OUTPUT_MODES = ('save', 'preview', 'queue')   # §21
JOB_STATES = ('queued', 'running', 'success', 'failed', 'cancelled')  # §22.1

# §20.2 — Presets enthalten keine Eingabedatei. Diese Schluessel (in jeder
# Ebene: Preset, Step, Params) werden kategorisch abgelehnt.
_FORBIDDEN_KEYS = re.compile(
    r'^(input|infile|in_file|file|source|src|path|filename|gcode_file)$', re.I)

# R260: Preset-Namen duerfen Umlaute tragen (Anzeige/RESPOND) — der
# Datei-Tag transliteriert sie (ae/oe/ue). Bewusst NUR diese sieben
# Zeichen, kein freies Unicode (Pfad-/Display-Sicherheit).
_PRESET_NAME_RE = re.compile(
    r'^[A-Za-z0-9ÄÖÜäöüß][A-Za-z0-9ÄÖÜäöüß _().+-]{0,63}$')
# R260: Ketten-Eingabe darf aus Unterordnern kommen (Range/V02_x.gcode) —
# §20.2 erweitert auf RELATIVE Pfade: kein fuehrendes '/', kein '..'
# (Segmente muessen alphanumerisch anfangen — Kletterei ist bauartlich
# unmoeglich), keine Laufwerks-/URL-Reste. Umlaut-Dateinamen sind legal
# (der Stem wird fuer die AUSGABE ohnehin transliteriert+sanitiert).
_INPUT_NAME_RE = re.compile(
    r'^(?:[A-Za-z0-9ÄÖÜäöüß][A-Za-z0-9ÄÖÜäöüß _().+-]*/)*'
    r'[A-Za-z0-9ÄÖÜäöüß][A-Za-z0-9ÄÖÜäöüß _().+-]*\.gcode$')

# R260: deutsche Umschrift VOR dem ASCII-Sanitize — generierte Namen bleiben
# auf jedem LCD und jeder SD-Karte lesbar: "Größer Rahmen" -> Groesser_Rahmen
# statt Gr_er_Rahmen. Zwillings-Map in r2_postproc._translit_name (Drift-
# Wächter in test_toolchain_steps).
_TRANSLIT = {
    'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
    'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
}


def _translit(text):
    return ''.join(_TRANSLIT.get(ch, ch) for ch in str(text))


def _sanitize_stem(name, dflt='MODEL'):
    """R260: Pendant zum Engine-_gen_stem (Transliteration + ASCII)."""
    st = re.sub(r'[^A-Za-z0-9._-]+', '_', _translit(name)).strip('_')
    return st or dflt


def _chain_tag(preset, limit=24):
    """R260: Preset-Name als Wortkette (CamelCase) fuer die ENDAUSGABE.

    "Scale up + twist" -> "ScaleUpTwist". Abgeschnitten wird an einer
    Wortgrenze (limit-Zeichen); gibt es kein Wort, bleibt der Tag aus.
    """
    words = re.findall(r'[A-Za-z0-9]+',
                       _translit(preset.get('name') or ''))
    parts, used = [], 0
    for word in words:
        word = word[0].upper() + word[1:]
        if parts and used + len(word) > limit:
            break
        parts.append(word)
        used += len(word)
    return ''.join(parts)[:limit]

# macros/17_generator.cfg:1179 — die 27 Muster-Codes (Reihenfolge dort).
TEXTURE_PATTERNS = (
    'RIDGES', 'WAVES', 'GRID', 'HATCH', 'CHECKER', 'HEX', 'HONEYCOMB',
    'BASKET', 'ROPE', 'PLANKS', 'BRICKS', 'SANDSTONE', 'CONCRETE', 'CLAY',
    'CREPE', 'FABRIC', 'PLUSH', 'HILBERT', 'SCRATCH', 'GLITCH', 'KNIT',
    'FLUTED', 'BARK', 'SCALES', 'FACETS', 'MACRAME', 'MAP',
    # R265/R265.3 (was never extended there - latent inconsistency):
    'STONEWALL', 'RUBBLE', 'TILES', 'PARQUET', 'LAMINATE', 'MAZE',
    'PERFORATION', 'VENT', 'CARBON', 'PINDOTS', 'OCTAGONS', 'CHAINLINK',
    'NETGRID',
    # R266.2 bite 3: organics
    'RINGS', 'OAK', 'BEECH', 'KNOT', 'OLDBARK', 'LEATHER', 'ORANGE',
    'CRACKS', 'WRINKLE',
    # R266.3 bite 4: decor & haptics
    'HEARTS', 'GOLF', 'BASKETBALL', 'RAUFASER', 'ROOFTILES', 'CROCHET',
)

# ---------------------------------------------------------------------------
# Menü-Zuordnung: LCD-Gruppe (letztes Segment der Menü-ID) -> Werkzeugname.
# Quelle: web/menu_structure.json, Baum __main __preprint __mods
# (Gruppen: __poff __tex __rng __scale __twist __mirror __cake __plot).
# cake: PART=BOTH erzeugt ZWEI Dateien (H3) -> outputs=2, in Ketten gesperrt.
# ---------------------------------------------------------------------------
MENU_TOOL_MAP = {
    '__rng':    {'name': 'range',   'title': 'Range — Schichtfenster (make_range:1937)'},
    '__tex':    {'name': 'texture', 'title': 'Texture — Muster auf Außenwand (17_generator:1178)'},
    '__scale':  {'name': 'scale',   'title': 'Scale — X/Y/Taper (lcd_menues:3883)'},
    '__cake':   {'name': 'cake',    'title': 'Cake — Schnitt (PART=BOTH: 2 Dateien, H3)',
                 'outputs': 2},
    '__twist':  {'name': 'twist',   'title': 'Twist — Verdrillen (lcd-Menü __twist)'},
    '__mirror': {'name': 'mirror',  'title': 'Mirror — Achse spiegeln (lcd-Menü __mirror)'},
    '__poff':   {'name': 'offset',  'title': 'Offset — XY/Z-Versetzen (lcd-Menü __poff; '
                                             'Parameter laufen nicht über SAVE_VARIABLE)'},
    '__plot':   {'name': 'plot',    'title': 'Plot — Plotter-Overrides (lcd-Menü __plot)'},
}

# Anreicherungen für die MENÜ-Registry (Pflicht/Regeln; die Menü-Daten
# kennen keine Pflichtfelder — das ist Engine-Wissen):
_MENU_ENRICHMENTS = {
    'range': {
        'required': ('range_start', 'range_end'),
        'rules': [{'a': 'range_start', 'b': 'range_end', 'op': 'le'}],
    },
    'scale': {'required': ('scale_x', 'scale_y'), 'rules': []},
    'texture': {'required': ('texture_scale', 'texture_zsize', 'texture_amp'),
                'rules': []},
}

# Alias-Brücke Anker-Registry <-> Menü-Variable (für den Drift-Wächter).
_ANCHOR_MENU_ALIASES = {
    'range': {'start': 'range_start', 'end': 'range_end',
              'floor': 'range_floor', 'top': 'range_top',
              'brim': 'range_brim', 'floor_hole': 'range_floor_hole',
              'top_hole': 'range_top_hole'},
    'scale': {'x': 'scale_x', 'y': 'scale_y',
              'top_x': 'scale_top_x', 'top_y': 'scale_top_y'},
    'texture': {'scale_mm': 'texture_scale', 'zsize_mm': 'texture_zsize',
                'depth_mm': 'texture_amp', 'seed': 'texture_seed'},
    'twist': {'deg': 'twist_deg'},
    'mirror': {},   # Achse ist Enum (x/y) vs. LCD-Index 0/1: keine
                    # Bereichs-Alteste vergleichbar; Zuordnung im Adapter
}

# ---------------------------------------------------------------------------
# Anker-Registry (Preset-Vertrag). Alle Bereiche GEGEN das LCD-Menü
# gesichert (registry_drift — CI-Test). range_start/-end Maximum ist im
# Menü dynamisch (total_layers-abhängig) -> statischer Fallback 9999.
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    'range': {
        'title': 'Range — Schichtfenster (make_range:1937)',
        'outputs': 1,
        'params': {
            'start': {'type': 'int', 'min': 2, 'max': 9999, 'required': True,
                      'note': 'Menü-Maximum dynamisch (total_layers)'},
            'end': {'type': 'int', 'min': 3, 'max': 9999, 'required': True,
                    'note': 'Menü-Maximum dynamisch (total_layers)'},
            'floor': {'type': 'int', 'min': 0, 'max': 10,
                      'required': False, 'default': 0},
            'top': {'type': 'int', 'min': 0, 'max': 10,
                    'required': False, 'default': 0},
            'brim': {'type': 'int', 'min': 0, 'max': 10,
                     'required': False, 'default': 0},
            'floor_hole': {'type': 'number', 'min': 0.0, 'max': 80.0,
                           'required': False, 'default': 0.0},
            'top_hole': {'type': 'number', 'min': 0.0, 'max': 80.0,
                         'required': False, 'default': 0.0},
        },
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
        'title': 'Texture — Muster auf Außenwand (17_generator.cfg:1178 ff.)',
        'outputs': 1,
        'params': {
            'pattern': {'type': 'enum', 'values': TEXTURE_PATTERNS,
                        'required': True},
            'scale_mm': {'type': 'number', 'min': 3.0, 'max': 80.0,
                         'required': True},
            'zsize_mm': {'type': 'number', 'min': 0.5, 'max': 200.0,
                         'required': True},
            'depth_mm': {'type': 'number', 'min': 0.05, 'max': 4.0,
                         'required': True},   # R266: >1.0 = DEEP RELIEF
            # lcd_menues.cfg:3458: LCD-Index 1 = OUT, 0 = IN;
            # Engine-Default 'OUT' (r2_postproc.py:28286).
            'direction': {'type': 'enum', 'values': ('IN', 'OUT'),
                          'required': False, 'default': 'OUT'},
            'seed': {'type': 'int', 'min': 1, 'max': 999,
                     'required': False, 'default': 1},
        },
        'rules': [],
    },
    'twist': {
        'title': 'Twist — um Z verdrillen (apply_twist:24186; LCD -720..720)',
        'outputs': 1,
        'params': {
            'deg': {'type': 'number', 'min': -720.0, 'max': 720.0,
                    'required': True},
        },
        'rules': [],
    },
    'mirror': {
        'title': 'Mirror — Achse spiegeln (apply_mirror:24442; '
                 'LCD-Index 0 = X, 1 = Y, lcd_menues.cfg:3981)',
        'outputs': 1,
        'params': {
            'axis': {'type': 'enum', 'values': ('x', 'y'), 'required': True},
        },
        'rules': [],
    },
    # R270 (J2): casting mold around the current file. The LCD-UI is the
    # GENERATOR menu (__main __gen __mold), not __mods - the anchor
    # registry is the contract (no menu mirror, like the enums below it
    # the ranges are engine law: make_mold clamps + refuses).
    'mold': {
        'title': 'Mold — Gießform um die Datei (make_mold R270/J2; '
                 'LCD-UI im Generator-Menü __gen __mold)',
        'outputs': 1,
        'params': {
            'wall': {'type': 'int', 'min': 3, 'max': 15,
                     'required': False, 'default': 5},
            'gap': {'type': 'number', 'min': 0.05, 'max': 0.30,
                    'required': False, 'default': 0.15},
            'pour': {'type': 'int', 'min': 5, 'max': 15,
                     'required': False, 'default': 8},
            'funnel': {'type': 'enum', 'values': ('NONE', 'CONICAL'),
                       'required': False, 'default': 'CONICAL'},
            'vent': {'type': 'number', 'min': 1.5, 'max': 4.0,
                     'required': False, 'default': 2.5},
            'pin': {'type': 'int', 'min': 3, 'max': 8,
                    'required': False, 'default': 3},
            'draft': {'type': 'number', 'min': 0.0, 'max': 3.0,
                      'required': False, 'default': 0.0},
            # R272: surface mode - chain-friendly (no output-count
            # change): STANDARD/FINE (ironing + 20mm/s)/FUZZY (matte)
            'surface': {'type': 'enum', 'values': ('STANDARD', 'FINE',
                                                   'FUZZY'),
                        'required': False, 'default': 'STANDARD'},
            # BOTH (2 Dateien) hat in Ketten keine Semantik (die Cake-
            # Regel) - der Enum lehnt es schon bei der Preset-Validierung
            # ab, der Adapter zur Laufzeit gleich mit
            'part': {'type': 'enum', 'values': ('TOP', 'BOTTOM'),
                     'required': False, 'default': 'TOP'},
            'plane': {'type': 'enum', 'values': ('AUTO', 'MID', 'OFF'),
                      'required': False, 'default': 'AUTO'},
            'zoff': {'type': 'number', 'min': -50.0, 'max': 250.0,
                     'required': False, 'default': 0.0},
            # R271: sector stage - in Ketten immer 0 gepinnt (die Regel
            # unten): 3/4-part schreibt MEHRERE Dateien (Stueck-Set) und
            # wird im LCD-Menue gebaut, nicht in der Kette. Typisiert +
            # sichtbar bleibt der Parameter, damit Presets eine klare
            # Meldung statt "unbekannt" kriegen.
            'sectors': {'type': 'int', 'min': 0, 'max': 2,
                        'required': False, 'default': 0,
                        'note': 'Ketten: nur 0 - 3/4-part = LCD-only'},
        },
        'rules': [{'a': 'sectors', 'op': 'is', 'value': 0,
                   'msg': '3/4-part schreibt ein Stueck-Set (mehrere '
                          'Dateien) - im Generator-Menue __gen __mold '
                          'bauen, nicht in der Kette'}],
    },

    # R273 (J2 bite 2): parametric BLANK mold - no input file needed
    # (the blank IS the source; the chain input is ignored). 16 params
    # = the cap: the rest (gap, pour, funnel, vent, pin, draft, zoff,
    # pocket dims) stays on the engine defaults - the LCD menu carries
    # the full set. part=BOTH (2 Dateien) und Sektoren (Stueck-Set)
    # bleiben wie beim mold in Ketten gesperrt.
    'mold_blank': {
        'title': 'Blank-Mold — parametrischer Grundkoerper (make_mold_'
                 'blank R273/J2; LCD-UI im Generator-Menue __gen __mold '
                 '__blank)',
        'outputs': 1,
        'params': {
            'shape': {'type': 'enum',
                      'values': ('MEDALLION', 'PLAQUE', 'BAR'),
                      'required': False, 'default': 'MEDALLION'},
            'dia': {'type': 'int', 'min': 15, 'max': 100,
                    'required': False, 'default': 40},
            'thick': {'type': 'number', 'min': 4.0, 'max': 25.0,
                      'required': False, 'default': 8.0},
            'width': {'type': 'int', 'min': 20, 'max': 150,
                      'required': False, 'default': 60},
            'height': {'type': 'int', 'min': 20, 'max': 150,
                       'required': False, 'default': 40},
            'corner': {'type': 'number', 'min': 0.0, 'max': 12.0,
                       'required': False, 'default': 4.0},
            'length': {'type': 'int', 'min': 30, 'max': 180,
                       'required': False, 'default': 90},
            'bar_w': {'type': 'int', 'min': 15, 'max': 90,
                      'required': False, 'default': 40},
            'bar_h': {'type': 'int', 'min': 10, 'max': 60,
                      'required': False, 'default': 25},
            'taper': {'type': 'number', 'min': 0.5, 'max': 1.0,
                      'required': False, 'default': 0.85},
            # relief seat depth in the cast top face (0 = plain blank);
            # the pocket DIMS default per shape (dia-10 / w-12 / h-12)
            'pocket_t': {'type': 'number', 'min': 0.0, 'max': 10.0,
                         'required': False, 'default': 2.0},
            'wall': {'type': 'int', 'min': 3, 'max': 15,
                     'required': False, 'default': 5},
            'surface': {'type': 'enum', 'values': ('STANDARD', 'FINE',
                                                   'FUZZY'),
                        'required': False, 'default': 'STANDARD'},
            'part': {'type': 'enum', 'values': ('TOP', 'BOTTOM'),
                     'required': False, 'default': 'TOP'},
            'plane': {'type': 'enum', 'values': ('AUTO', 'MID', 'OFF'),
                      'required': False, 'default': 'OFF'},
            'sectors': {'type': 'int', 'min': 0, 'max': 2,
                        'required': False, 'default': 0,
                        'note': 'Ketten: nur 0 - 3/4-part = LCD-only'},
        },
        'rules': [{'a': 'sectors', 'op': 'is', 'value': 0,
                   'msg': '3/4-part schreibt ein Stueck-Set (mehrere '
                          'Dateien) - im Generator-Menue __gen __mold '
                          'bauen, nicht in der Kette'}],
    },
}


# ---------------------------------------------------------------------------
# Menü-Daten laden und Registry ableiten
# ---------------------------------------------------------------------------

def load_menu_data(path=None):
    """Laedt den Menü-Export (web/menu_structure.json — Quelle der Wahrheit,
    exportiert von tools/menu_json_export.py)."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'web', 'menu_structure.json')
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def _walk(node):
    yield node
    for child in node.get('children') or []:
        yield from _walk(child)


def _find_node(root, node_id):
    for node in _walk(root):
        if node.get('id') == node_id:
            return node
    return None


def _save_variable(gcode_lines):
    for line in gcode_lines or []:
        match = re.search(r'SAVE_VARIABLE VARIABLE=([A-Za-z0-9_]+)', line)
        if match:
            return match.group(1)
    return None


def _static_number(value):
    """LCD-Werte sind Strings; Jinja-Ausdrücke sind dynamisch -> None."""
    if not isinstance(value, str) or '{' in value or '}' in value:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return int(number) if number == int(number) else number


def _param_spec(node):
    step = _static_number(node.get('input_step'))
    lo = _static_number(node.get('input_min'))
    hi = _static_number(node.get('input_max'))
    kind = 'int' if isinstance(step, int) else 'number'
    spec = {'type': kind, 'required': False}
    if lo is not None:
        spec['min'] = lo
    if hi is not None:
        spec['max'] = hi
    if step is not None:
        spec['step'] = step
    if lo is None or hi is None:
        spec['note'] = 'Menü-Grenze dynamisch (Jinja) — Bereichsprüfung ausgesetzt'
    return spec


def build_registry(menu_data):
    """Vollständige Werkzeug-Registry aus den MENÜ-DATEN (8 Mods-Werkzeuge).

    Parameternamen sind die SAVE_VARIABLE-Namen des LCD. Pflichtfelder und
    Querschnittsregeln kommen aus _MENU_ENRICHMENTS (Engine-Wissen, im
    Quelltext mit Fundstelle). Das texture-Muster ist kein LCD-Input
    (Auswahl läuft über Presets) und wird als Enum ergänzt.
    """
    mods = _find_node(menu_data['tree'], '__main __preprint __mods')
    if mods is None:
        raise ValueError('Menübaum kennt __main __preprint __mods nicht')
    registry = {}
    for group in mods.get('children') or []:
        group_id = group.get('id', '').split()[-1]
        meta = MENU_TOOL_MAP.get(group_id)
        if meta is None:
            continue
        params = {}
        for child in group.get('children') or []:
            if child.get('type') != 'input':
                continue
            var = _save_variable(child.get('gcode'))
            if var is None:
                continue          # z. B. __rng __stop: kein Zustandsparameter
            params[var] = _param_spec(child)
        enrich = _MENU_ENRICHMENTS.get(meta['name'], {})
        for name in enrich.get('required', ()):
            if name in params:
                params[name]['required'] = True
        if meta['name'] == 'texture':
            params['pattern'] = {'type': 'enum', 'values': TEXTURE_PATTERNS,
                                 'required': True,
                                 'note': 'kein LCD-Input — Preset-Auswahl '
                                         '(17_generator.cfg:1179)'}
        registry[meta['name']] = {
            'title': meta['title'],
            'outputs': meta.get('outputs', 1),
            'params': params,
            'rules': list(enrich.get('rules', [])),
        }
    return registry


def registry_drift(registry=None, menu_data=None):
    """Wächter gegen stille Menü-Änderungen: vergleicht die Anker-Registry
    mit den Menü-Daten (Aliase siehe _ANCHOR_MENU_ALIASES). Leer == konsistent.
    Nur GEMEINSAME Parameter werden verglichen; dynamische Menü-Grenzen
    werden übersprungen (aber gemeldet, wenn der Anker eine statische
    Grenze behauptet, wo das Menü dynamisch ist)."""
    if registry is None:
        registry = TOOL_REGISTRY
    if menu_data is None:
        menu_data = load_menu_data()
    menu_registry = build_registry(menu_data)
    drift = []
    for tool, aliases in _ANCHOR_MENU_ALIASES.items():
        if tool not in menu_registry:
            drift.append('Werkzeug %r fehlt in den Menüdaten' % tool)
            continue
        menu_params = menu_registry[tool]['params']
        for anchor_name, menu_name in aliases.items():
            anchor_spec = registry[tool]['params'].get(anchor_name)
            menu_spec = menu_params.get(menu_name)
            if anchor_spec is None or menu_spec is None:
                drift.append('%s: Parameter %r/%r fehlt auf einer Seite'
                             % (tool, anchor_name, menu_name))
                continue
            for bound in ('min', 'max'):
                a_val = anchor_spec.get(bound)
                m_val = menu_spec.get(bound)
                if bound in menu_spec and 'note' in menu_spec:
                    continue          # dynamische Menü-Grenze: nicht vergleichbar
                if a_val is not None and m_val is not None and a_val != m_val:
                    drift.append('%s.%s: Anker-%s=%r != Menü-%s=%r'
                                 % (tool, anchor_name, bound, a_val,
                                    bound, m_val))
    return drift


# ---------------------------------------------------------------------------
# Preset-Vertrag (Phase 1)
# ---------------------------------------------------------------------------

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


def _validate_params(tool, params, where, errors, registry):
    if not isinstance(params, dict):
        errors.append('%s: "params" muss ein Objekt sein' % where)
        return
    _check_forbidden(params, where + '.params', errors)
    spec = registry[tool]['params']
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
    for rule in registry[tool].get('rules', ()):
        a = params.get(rule['a'])
        b = params.get(rule['b']) if 'b' in rule else None
        if rule['op'] == 'is':
            # fester Wert (kein zweiter Parameter) - R271: mold-sectors
            # ist in Ketten auf 0 gepinnt (Mehr-Datei-Ausgaben sind die
            # Cake-Regel), der Parameter bleibt sichtbar + typisiert
            if a is not None and a != rule.get('value'):
                errors.append('%s: "%s" muss %s sein (%s)'
                              % (where, rule['a'], rule.get('value'),
                                 rule.get('msg', 'Kettenregel')))
            continue
        if _is_number(a) and _is_number(b):
            if rule['op'] == 'le' and not a <= b:
                errors.append('%s: "%s" (%r) muss <= "%s" (%r) sein'
                              % (where, rule['a'], a, rule['b'], b))


def validate_preset(preset, registry=None):
    """Prueft ein Toolchain-Preset gegen den Vertrag.

    Rueckgabe: (ok_bool, errors_liste) — Fehler sind Klartext mit
    Schritt-Bezug, niemals eine Ausnahme. Keine Datei wird angefasst.
    """
    if registry is None:
        registry = TOOL_REGISTRY
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
        if tool not in registry:
            errors.append('%s: unbekanntes Werkzeug %r (registriert: %s)'
                          % (where, tool, ', '.join(sorted(registry))))
            continue
        if registry[tool].get('outputs', 1) != 1:
            errors.append('%s: Werkzeug "%s" erzeugt mehrere Ausgaben — '
                          'in Ketten (noch) nicht zulaessig' % (where, tool))
        if 'params' in step:
            _validate_params(tool, step['params'], where, errors, registry)
        else:
            errors.append('%s: "params" fehlt' % where)

    return not errors, errors


def _effective_params(tool, params, registry):
    spec = registry[tool]['params']
    merged = dict(params or {})
    for name, pspec in spec.items():
        if name not in merged and 'default' in pspec:
            merged[name] = pspec['default']
    return merged


def plan_chain(preset, input_name, registry=None, first_version=1):
    """Baut den reinen Ausfuehrungsplan: welche Jobs, in welcher Reihenfolge,

    mit welcher Ein-/Ausgabe-Datei und welchem Temp-/Gate-Status. Fuehrt
    NICHTS aus und schreibt keine Datei.

    first_version (R259, System-Anbindung): die V-Nummer des ERSTEN
    Schritts. Der Watcher uebergibt _next_gen_version(Ausgabeordner), so
    dass aufeinanderfolgende Laeufe nie auf eine existierende Endausgabe
    treffen (§22: nichts wird ueberschrieben). Default 1 = K2a-Verhalten.
    """
    if registry is None:
        registry = TOOL_REGISTRY
    if not isinstance(first_version, int) or first_version < 1:
        return None, ['first_version muss eine ganze Zahl >= 1 sein '
                      '(got %r)' % (first_version,)]
    ok, errors = validate_preset(preset, registry)
    if not ok:
        return None, errors
    if not isinstance(input_name, str) or not _INPUT_NAME_RE.match(input_name):
        return None, ['Eingabedatei %r ist kein relativer .gcode-Pfad im '
                      'Gcodes-Ordner (Unterordner ok, kein .. / absoluter '
                      'Pfad — §20.2/R260: die Auswahl trifft der Nutzer '
                      'zur Laufzeit)' % input_name]

    # R260: Stem = sanitierter BASENAME (Unterordner-Eingaben!), ein
    # fuehrendes V<nn>_ einer vorigen Werkzeug-Ausgabe faellt weg — die
    # Kette setzt ihre eigene Versionsnummer davor.
    stem = _sanitize_stem(
        os.path.basename(input_name)[:-len('.gcode')])
    stem = re.sub(r'^V\d+_', '', stem) or stem
    tag = _chain_tag(preset)
    steps = []
    current_input = input_name
    for idx, step in enumerate(preset['steps'], start=1):
        tool = step['tool']
        output = 'V%02d_%s.gcode' % (first_version + idx - 1, stem)
        if idx == len(preset['steps']) and tag:
            # R260: nur die ENDAUSGABE traegt den Preset-Namen — die
            # temporaeren Zwischenstaende sterben doch (§22.4)
            output = 'V%02d_%s_%s.gcode' % (first_version + idx - 1,
                                            stem, tag)
        job = {
            'job': idx,
            'tool': tool,
            'title': registry[tool]['title'],
            'params': _effective_params(tool, step.get('params'), registry),
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
        'output_dir': 'Toolchain/',   # R259: Watcher-Verhalten (_gensub)
        'naming': 'V<nn>_<stem>[_<PresetWortkette>].gcode (R259: nn = '
                  'first_version + Schritt - 1, der Watcher uebergibt die '
                  'naechste freie Nummer; R260: Stem = sanitierter Basis- '
                  'name der Eingabe (Umlaute ae/oe/ue, V<nn>_ einer '
                  'Vorgaenger-Ausgabe faellt weg), der Preset-Name als '
                  'Wortkette haengt NUR an der Endausgabe)',
        'steps': steps,
        'final_output': steps[-1]['output'],
        'temp_outputs': sum(1 for s in steps if s['temp']),
        'limits': [
            'Plan ohne Ausfuehrung — Toolchain-Konzept Phase 2a '
            '(analyse/TOOLCHAIN-KONZEPT.md)',
            'Job N+1 startet erst nach validierter Ausgabe von Job N '
            '(§20.3/§22.4) — run_chain setzt das durch',
            'Temporaere Zwischenstaende werden erst geloescht, wenn der '
            'Naechste sie uebernommen hat (§22.4)',
            'Original bleibt unveraendert (§20.2)',
        ],
    }
    return plan, []


def load_preset_file(path, registry=None):
    """R259 (Phase 2b/2): Preset-DATEI laden und validieren.

    Die Preset-Auswahl am LCD ist ein DATEI-Pick (SD-Browser klickt ein
    .json an, macros/13_system.cfg SDNAV_GO) — hier entsteht daraus das
    Preset-Diktat: Lesefehler, JSON-Fehler und Vertragverletzungen werden
    zu Klartext-Fehlern (keine Ausnahme), damit der Watcher sie als
    NOTIFY/M117 melden kann. Offline testbar, fasst nichts an.

    Rueckgabe: (preset|None, errors_liste) — preset ist nur bei leerer
    Fehlerliste nicht None.
    """
    if not os.path.isfile(path):
        return None, ['Preset-Datei fehlt: %s' % path]
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            preset = json.load(handle)
    except OSError as err:
        return None, ['Preset nicht lesbar: %s (%s)' % (path, err)]
    except json.JSONDecodeError as err:
        return None, ['Preset ist kein gueltiges JSON: %s (Zeile %d, '
                      'Spalte %d)' % (err.msg, err.lineno, err.colno)]
    ok, errors = validate_preset(preset, registry)
    if not ok:
        return None, ['%s: %s' % (os.path.basename(path), e) for e in errors]
    return preset, []


def registry_report(registry=None):
    """Kurzbericht ueber eine Registry (fuer Tests und spaetige UI-Anzeige)."""
    if registry is None:
        registry = TOOL_REGISTRY
    report = {}
    for tool, spec in registry.items():
        report[tool] = {
            'title': spec['title'],
            'outputs': spec.get('outputs', 1),
            'params': sorted(spec['params']),
            'required': sorted(p for p, v in spec['params'].items()
                               if v.get('required')),
        }
    return report


# ---------------------------------------------------------------------------
# Ausführungs-Engine (Phase 2a) — §21/§22
# ---------------------------------------------------------------------------

def default_validator(path):
    """§22.1-Erfolgsbegriff: Die Datei existiert, ist lesbar und nicht leer.

    Rueckgabe None = ok, sonst Klartext-Fehler.
    """
    if not os.path.exists(path):
        return 'Ausgabe fehlt: %s' % path
    if os.path.getsize(path) <= 0:
        return 'Ausgabe ist leer: %s' % path
    try:
        with open(path, 'rb') as handle:
            handle.read(1)
    except OSError as err:
        return 'Ausgabe nicht lesbar: %s (%s)' % (path, err)
    return None


def run_chain(plan, workspace, input_path, step_runner,
              validator=None, output_mode='save', on_output=None,
              cancel_check=None, on_step=None):
    """Fuehrt einen PLAN aus — mit den Gates aus dem Gesamtbriefing.

    Vertrag:
      plan         — Ergebnis von plan_chain() (schema-geprueft)
      workspace    — Zielordner fuer die Vnn_-Ausgaben (wird angelegt);
                     existiert die ENDAUSGabe schon, wird NOTHING ueberschrieben
      input_path   — Pfad zur ausgewaehlten Originaldatei (bleibt unveraendert)
      step_runner  — callable(step, input_path, output_path); Erfolg = keine
                     Ausnahme; die Funktion MUSS die Ausgabedatei erzeugen
      validator    — callable(path) -> None|Fehlertext (Default: §22.1-Pruefung)
      output_mode  — 'save'|'preview'|'queue' (§21); preview/queue rufen den
                     on_output-Hook auf — schlaegt der fehl, gilt die Kette
                     als FAILED (§22.1: korrekt registriert)
      cancel_check — callable(schritt_index, 1-basiert) -> True bricht ab
      on_step      — callable(idx, gesamt, werkzeug), gerufen wenn Schritt
                     idx ZU ARBEITEN BEGINNT (R261: Fortschritt am LCD,
                     'Chain 2/3: Twist'). Kosmetik: ein Fehler im Hook
                     wird geschluckt — anders als on_output, dessen
                     Scheitern die Registrierung und damit die Kette
                     verfaelschen wuerde

    Rueckgabe: Laufbericht (dict, schema r2-toolchain-run/1) mit den
    Zustaenden queued/running/success/failed/cancelled je Schritt (§22.1).
    Temporaere Zwischenstaende werden erst NACH validierter Uebernahme durch
    den Nachfolger geloescht (§22.4); bei Fehler/Abbruch bleiben sie zur
    Nachvollziehbarkeit liegen.
    """
    if not isinstance(plan, dict) or plan.get('schema') != PLAN_SCHEMA:
        raise ValueError('plan ist kein %s-Plan (erst plan_chain rufen)'
                         % PLAN_SCHEMA)
    if output_mode not in OUTPUT_MODES:
        raise ValueError('output_mode %r ungueltig (erlaubt: %s)'
                         % (output_mode, ', '.join(OUTPUT_MODES)))
    if validator is None:
        validator = default_validator

    os.makedirs(workspace, exist_ok=True)
    records = [{'job': s['job'], 'tool': s['tool'], 'state': 'queued',
                'output': os.path.join(workspace, s['output']),
                'error': None, 'seconds': None}
               for s in plan['steps']]
    final_path = os.path.join(workspace, plan['steps'][-1]['output'])
    temp_deleted = []
    started = time.monotonic()

    def finish(state, error=None):
        return {
            'schema': RUN_SCHEMA,
            'ok': state == 'success',
            'state': state,
            'error': error,
            'steps': records,
            'temp_deleted': temp_deleted,
            'final_output': final_path if state == 'success' else None,
            'output_mode': output_mode,
            'duration_s': round(time.monotonic() - started, 3),
        }

    # Kein Ueberschreiben: existiert die Endausgabe, laeuft gar nichts an.
    if os.path.exists(final_path):
        return finish('failed',
                      'Endausgabe existiert bereits — nichts wird '
                      'ueberschrieben: %s' % final_path)

    # §22.1 gilt auch fuer die Eingabe: sie muss existieren und lesbar sein.
    input_error = validator(input_path)
    if input_error is not None:
        return finish('failed', 'Eingabedatei unbrauchbar: %s' % input_error)

    for idx, step in enumerate(plan['steps'], start=1):
        if cancel_check is not None and cancel_check(idx):
            return finish('cancelled',
                          'Abbruch vor Schritt %d (Nutzer/Queue)' % idx)
        record = records[idx - 1]
        record['state'] = 'running'
        if on_step is not None:
            # R261: Fortschritt JE SCHRITT (Start-Semantik: der Hook feuert,
            # BEVOR der Schritt laeuft - das LCD sagt die Wahrheit ueber
            # den Moment). Kosmetik: Fehler im Hook werden geschluckt.
            try:
                on_step(idx, len(plan['steps']), step['tool'])
            except Exception:                        # noqa: BLE001 — Kosmetik
                pass
        in_path = (input_path if idx == 1
                   else os.path.join(workspace, step['input']))
        try:
            step_runner(step, in_path, record['output'])
        except Exception as err:                    # noqa: BLE001 — Bericht, kein Crash
            record['state'] = 'failed'
            record['error'] = '%s: %s' % (type(err).__name__, err)
            return finish('failed',
                          'Schritt %d (%s) gescheitert: %s'
                          % (idx, step['tool'], record['error']))
        step_error = validator(record['output'])
        if step_error is not None:
            record['state'] = 'failed'
            record['error'] = step_error
            return finish('failed',
                          'Validierung von Schritt %d (%s) fehlgeschlagen: %s'
                          % (idx, step['tool'], step_error))
        record['state'] = 'success'
        record['seconds'] = None   # Messwert folgt mit der System-Anbindung
        # §22.4: Vorgaenger-Zwischenstand erst JETZT loeschen — der
        # Nachfolger hat ihn erfolgreich uebernommen.
        if idx > 1:
            prev = plan['steps'][idx - 2]
            if prev.get('temp'):
                prev_path = os.path.join(workspace, prev['output'])
                if os.path.exists(prev_path):
                    os.remove(prev_path)
                    temp_deleted.append(prev_path)

    # §21/§22.1: Ausgabemodus. save = nur ablegen; preview/queue muessen
    # registriert werden — ein scheiternder Hook macht die Kette FAILED.
    if output_mode in ('preview', 'queue'):
        if on_output is None:
            return finish('failed',
                          'output_mode %r braucht einen on_output-Hook'
                          % output_mode)
        try:
            on_output(output_mode, final_path)
        except Exception as err:                    # noqa: BLE001
            return finish('failed',
                          'Ausgabemodus %r nicht registriert: %s: %s'
                          % (output_mode, type(err).__name__, err))

    return finish('success')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Toolchain-Preset validieren, planen und die Registry '
                    'gegen die Menüdaten pruefen (keine Ausfuehrung)')
    parser.add_argument('preset', nargs='?', default=None,
                        help='Pfad zur Preset-JSON-Datei')
    parser.add_argument('--input', default=None,
                        help='ausgewaehlte .gcode-Datei (nur fuer den Plan; '
                             'gehoert NIEMALS ins Preset selbst, §20.2)')
    parser.add_argument('--registry-report', action='store_true',
                        help='Registry aus den Menüdaten ableiten und den '
                             'Drift gegen die Anker ausgeben')
    args = parser.parse_args(argv)

    result = {}
    if args.registry_report:
        menu_data = load_menu_data()
        menu_registry = build_registry(menu_data)
        result['menu_registry'] = registry_report(menu_registry)
        result['drift'] = registry_drift(menu_data=menu_data)
        result['drift_ok'] = not result['drift']
    if args.preset:
        with open(args.preset, 'r', encoding='utf-8') as handle:
            preset = json.load(handle)
        ok, errors = validate_preset(preset)
        result.update({'schema': SCHEMA, 'ok': ok, 'errors': errors})
        if ok and args.input:
            plan, plan_errors = plan_chain(preset, args.input)
            result['plan'] = plan
            result['errors'] = list(result['errors']) + list(plan_errors)
            result['ok'] = plan is not None
    if not result:
        parser.error('preset oder --registry-report angeben')
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write('\n')
    if 'ok' in result:
        return 0 if result['ok'] else 1
    return 0 if result.get('drift_ok') else 1


if __name__ == '__main__':
    sys.exit(main())
