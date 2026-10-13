#!/usr/bin/env python3
# Validator: parst alle .cfg des Pakets und prueft:
#  1) Jinja2-Syntax aller Templates (gcode:, name:, enable:, input:, description:...)
#  2) variable_-Zeilen sind gueltige Python-Literale
#  3) SET_GCODE_VARIABLE VARIABLE=<name> -> declared in [gcode_macro _STATE]?
#  4) SAVE_VARIABLE VARIABLE=<name> -> wird in _INIT_DEFAULTS gesetzt (Info)
#  5) Menu-Sektionen: type vorhanden, Strings balanciert
import re, sys, glob, ast

try:
    from jinja2 import Environment, BaseLoader
except ImportError:
    print("jinja2 fehlt"); sys.exit(2)

# KIPPERS Jinja-Dialekt (wie klippy): Ausdruecke {x} in EINZELNEN Klammern,
# Bloecke {% x %}. {{ x }} waere hier ungueltig -> genau wie im echten Klipper.
env = Environment(
    loader=BaseLoader(),
    variable_start_string='{', variable_end_string='}',
    block_start_string='{%', block_end_string='%}',
)
fehler = []
warnungen = []

def parse_cfg(pfad):
    """Liefert Liste von (sektion, key, wert_zeilen)."""
    sektionen = []
    cur = None
    for nr, roh in enumerate(open(pfad, encoding='utf-8'), 1):
        zeile = roh.rstrip('\n')
        if not zeile.strip() or zeile.strip().startswith('#'):
            continue
        m = re.match(r'^\s*\[([^\]]+)\]', zeile)
        if m:
            cur = {'name': m.group(1), 'zeile': nr, 'keys': []}
            sektionen.append(cur)
            continue
        if cur is None:
            continue
        km = re.match(r'^(\s*)([A-Za-z_0-9 ]+):(.*)$', zeile)
        if km and (km.group(1) == '' or not cur['keys'] or km.group(2) not in ('',)):
            # neuer Schluessel (Spalte 0) oder Fortsetzung innerhalb Block: wir nehmen nur neue keys
            if km.group(1) == '':
                cur['keys'].append({'key': km.group(2), 'wert': km.group(3), 'zeile': nr, 'block': [km.group(3)]})
            else:
                # eingerueckte Zeile: Fortsetzung des letzten Keys
                if cur['keys']:
                    cur['keys'][-1]['block'].append(zeile.strip())
        else:
            if cur['keys'] and zeile.startswith((' ', '\t')):
                cur['keys'][-1]['block'].append(zeile.strip())
    return sektionen

def klipper_strip(txt):
    # EXAKT wie klippy/configfile.py ('Strip trailing comments'): jede Zeile
    # wird beim ERSTEN '#' abgeschnitten - auch mitten in gcode-Blocks!
    return '\n'.join(l[:l.find('#')] if '#' in l else l for l in txt.split('\n'))

def pruefe_template(txt, wo):
    roh = txt.strip()
    if not roh or ('{' not in roh and '{%' not in roh):
        return
    if '{#' in roh:
        fehler.append(f"{wo}: Jinja comment {{# ... #}} FORBIDDEN! Klipper cuts every "
                      f"line at the first '#' -> an orphan '{{' remains -> template dies "
                      f"with \"unexpected '%'\". Use a separate '#' comment line instead.")
        return
    # So wie Klipper die Datei wirklich liest: erst Kommentar-Strip, dann Jinja
    gelesen = klipper_strip(roh)
    try:
        _ast_v = env.parse(gelesen)
    except Exception as e:
        fehler.append(f"{wo}: Jinja error (after Klipper comment strip): {e}\n    >>> {gelesen[:160]}")
        return

    # R130 (Boot-Blocker-Klasse .47/.90): unbekannte Filter/Tests. Jinja >= 3.1
    # kompiliert sie STILL (der Fehler erscheint erst beim Laden auf dem
    # Printer = 'Internal error during connect') - daher statischer AST-Walk:
    # jeder Filter-/Test-Name muss in den realen Jinja-Tabellen existieren.
    import jinja2.nodes as _jnodes
    _bad_v = []

    def _walk_v(n):
        if isinstance(n, _jnodes.Filter):
            if n.name not in env.filters:
                _bad_v.append('filter ' + n.name)
        elif isinstance(n, _jnodes.Test):
            if n.name not in env.tests:
                _bad_v.append('test ' + n.name)
        for c in n.iter_child_nodes():
            _walk_v(c)

    _walk_v(_ast_v)
    if _bad_v:
        fehler.append(f"{wo}: unknown Jinja {', '.join(sorted(set(_bad_v)))} - "
                      f"Klipper fails loading this template AT BOOT")


import re as _reM



def scan_hash_in_quotes(pfad):
    """R65: ein '#' nach einer ungeraden Anzahl Quotes = Klipper schneidet die
    Zeile mitten im String ab -> 'unterminated string literal' / kaputtes
    Template -> Printer halted. Genau das passierte mit variable_charset (.47)."""
    for nr, roh in enumerate(open(pfad, encoding='utf-8'), 1):
        zeile = roh.rstrip('\n')
        st = zeile.lstrip()
        h = st.find('#')
        if h <= 0:          # kein '#' oder reiner Kommentar
            continue
        davor = st[:h]
        if davor.count('"') % 2 == 1:
            fehler.append(f"{pfad}:{nr}: '#' inside a double-quoted string - Klipper cuts the "
                          f"line at '#' (unterminated string / broken template): {st[:70]}")
        if davor.count("'") % 2 == 1 and ('{' in davor or st.startswith('variable_')):
            fehler.append(f"{pfad}:{nr}: '#' inside a single-quoted template string - Klipper "
                          f"cuts the line at '#': {st[:70]}")

def scan_semicolon_in_quotes(pfad):
    """R114 (.87 field log): ein ';' INNERHALB eines Strings - Klipper schneidet
    JEDE Zeile am ersten ';' ab (auch mitten in Anfuehrungszeichen!) -> die
    RESPOND-Zeile endet ohne schliessendes Quote = 'Malformed command'. Im
    Feld: 'File features: DERIVED by geometry ... - no' (abgeschnitten bei
    ';TYPE:'). Analog zur R65-'#'-Regel, gleiche Heuristik."""
    for nr, roh in enumerate(open(pfad, encoding='utf-8'), 1):
        zeile = roh.rstrip('\n')
        st = zeile.lstrip()
        if st.startswith(('#', ';')):
            continue
        sm = st.find(';')
        if sm <= 0:
            continue
        # Jinja-Block-Tags ({% ... %}) erzeugen KEINE Ausgabezeile - ein ';'
        # darin ist Jinja-Code (z.B. |replace(';', '')), kein G-code-String
        _in_tag = False
        _pos = 0
        while True:
            a = st.find('{%', _pos)
            if a < 0:
                break
            b = st.find('%}', a)
            if b < 0:
                b = len(st)
            if a < sm < b + 2:
                _in_tag = True
                break
            _pos = b + 2
        if _in_tag:
            continue
        davor = st[:sm]
        if davor.count('"') % 2 == 1:
            fehler.append(f"{pfad}:{nr}: ';' inside a double-quoted string - Klipper cuts "
                          f"every line at the first ';' (Malformed command, .87 field log): {st[:70]}")
        if davor.count("'") % 2 == 1 and ('{' in davor or st.startswith('variable_')):
            fehler.append(f"{pfad}:{nr}: ';' inside a single-quoted template string - Klipper "
                          f"cuts the line at ';': {st[:70]}")

def main():
    dateien = sorted(glob.glob('macros/*.cfg') + glob.glob('menus/*.cfg') + glob.glob('*.example'))
    deklariert = set()   # _STATE variables
    save_keys = set()    # SAVE_VARIABLE-Namen
    set_gcv = {}         # VARIABLE -> (datei, zeile)
    menu_paths = {}      # R44: Menu-Sektionen -> Parent-Pruefung

    for pfad in dateien:
        scan_hash_in_quotes(pfad)
        scan_semicolon_in_quotes(pfad)
        # ---- R44: verklebte Menu-Header (Header in Kommentarzeile = Sektion unsichtbar!) ----
        if pfad.startswith('menus/'):
            for _i, _l in enumerate(open(pfad, encoding='utf-8').read().splitlines(), 1):
                # R63: '[menu.input]' in a name expression is NOT a glued header -
                # only flag '[menu ...]' / '[menu]' shapes
                if _reM.search(r'\[menu[ \]]', _l) and not _l.startswith('[menu'):
                    fehler.append(f"{pfad}:{_i}: verklebter Menu-Header: ...{_l.strip()[-70:]}")
        for sek in parse_cfg(pfad):
            name = sek['name']
            if name.startswith('gcode_macro') or name.startswith('delayed_gcode'):
                for k in sek['keys']:
                    if k['key'].startswith('variable_'):
                        vname = k['key'][len('variable_'):]
                        # R65: Klipper cuts EVERY line at '#' BEFORE literal_eval -
                        # a '#' inside the quoted string halted the printer (.47/.48)!
                        wert = klipper_strip('\n'.join(k['block'])).strip() or 'None'
                        try:
                            ast.literal_eval(wert)
                        except Exception as e:
                            fehler.append(f"{pfad}:{k['zeile']}: variable_{vname} not a valid literal "
                                          f"after Klipper '#' comment strip: {str(e)[:60]}: {wert[:80]}")
                    if k['key'].startswith('variable_'):
                        # variable_-Zeilen sind Python-Literale (kein Jinja!) -
                        # Literal-Gueltigkeit wurde oben schon geprueft
                        continue
                    text = '\n'.join(k['block'])
                    pruefe_template(text, f"{pfad}:{k['zeile']} [{name}] {k['key']}")
                    if k['key'] in ('gcode',):
                        for m in re.finditer(r'SET_GCODE_VARIABLE\s+MACRO=_STATE\s+VARIABLE=(\w+)', text):
                            set_gcv[m.group(1)] = (pfad, k['zeile'])
                        if name == 'gcode_macro _STATE':
                            pass
                        for m in re.finditer(r'SAVE_VARIABLE\s+VARIABLE=(\w+)', text):
                            save_keys.add(m.group(1))
                if name == 'gcode_macro _STATE':
                    for k in sek['keys']:
                        if k['key'].startswith('variable_'):
                            deklariert.add(k['key'][len('variable_'):])
            elif name.startswith('menu'):
                typ = None
                for k in sek['keys']:
                    text = '\n'.join(k['block'])
                    if k['key'] == 'type':
                        typ = k['wert'].strip()
                    if k['key'] in ('name', 'enable', 'input', 'gcode', 'index'):
                        pruefe_template(text, f"{pfad}:{k['zeile']} [{name}] {k['key']}")
                    # unbalancierte EINFACHE quotes koennten Template-Strings sein -> nur Doppel-Quote-Balance
                    if k['key'] == 'name':
                        w = k['wert'].strip()
                        if w.startswith("'") and not w.endswith("'"):
                            fehler.append(f"{pfad}:{k['zeile']}: unbalanced quotes in name: {w[:80]}")
                if typ is None and name != 'menu':
                    fehler.append(f"{pfad}:{sek['zeile']} [{name}]: type missing")
                # ---- R44: Klipper-Halt-Schutz (name fehlt = 'Printer is halted') ----
                _mk = [k['key'] for k in sek['keys']]
                if 'name' not in _mk:
                    fehler.append(f"{pfad}:{sek['zeile']} [{name}]: 'name' fehlt -> KLIPPER-HALT!")
                _dup = sorted({x for x in _mk if _mk.count(x) > 1})
                if _dup:
                    fehler.append(f"{pfad}:{sek['zeile']} [{name}]: doppelte Option(en): {','.join(_dup)}")
                menu_paths[name[5:] if name.startswith('menu ') else name] = (pfad, sek['zeile'])

    # ---- R44: Parent-Sektion muss existieren (sonst LCD-Eintrag unerreichbar) ----
    for _name, (_p, _z) in menu_paths.items():
        if ' ' in _name:
            _parent = _name.rsplit(' ', 1)[0]
            if _parent not in menu_paths:
                fehler.append(f"{_p}:{_z} [{_name}]: Parent [{_parent}] fehlt -> Eintrag unerreichbar!")

    # SET_GCODE_VARIABLE gegen Deklaration
    for var, (pfad, zeile) in set_gcv.items():
        if var not in deklariert:
            fehler.append(f"{pfad}:{zeile}: SET_GCODE_VARIABLE VARIABLE={var} not declared in _STATE!")

    # ---- rename-Typ-Kompatibilitaet (Klipper: 'different types' Check) --------------
    def is_traditional(cmd):
        # exakt wie klippy/gcode.py is_traditional_gcode():
        try:
            c = cmd.upper().split()[0]
            float(c[1:])
            return c[0].isupper() and c[1].isdigit()
        except Exception:
            return False
    for pfad in dateien:
        for sek in parse_cfg(pfad):
            if not sek['name'].startswith('gcode_macro '):
                continue
            alias = sek['name'].split(' ', 1)[1]
            for k in sek['keys']:
                if k['key'] == 'rename_existing':
                    ziel = k['wert'].strip()
                    if is_traditional(alias) != is_traditional(ziel):
                        fehler.append(
                            f"{pfad}:{k['zeile']}: rename_existing '{ziel}' hat anderen Typ als "
                            f"'{alias}' -> Klipper: \"G-Code macro rename of different types\". "
                            f"Bei M/G-Codes (Buchstabe+Zahl) muss auch der Zielname rein Zahlen "
                            f"nach dem Buchstaben haben (z.B. M104 -> M99104, NICHT M104_BASE).")

    # ---- Gueltige Befehlsnamen (Klipper: "Can't register ... invalid name") ---------
    # benannte Befehle muessen: GROSSBUCHSTABEN sein, nur [A-Z0-9_] enthalten und
    # duerfen KEINE Ziffer an Position 1 oder 2 haben (Ziffern erst ab Stelle 3).
    # Traditionelle G-Codes (Buchstabe+Zahl, z.B. M99104) sind davon ausgenommen.
    for pfad in dateien:
        for sek in parse_cfg(pfad):
            n = sek['name']
            if n.startswith('gcode_macro ') or n.startswith('delayed_gcode '):
                cmd = n.split(' ', 1)[1]
                if not is_traditional(cmd):
                    if not (cmd == cmd.upper() and cmd.replace('_', 'A').isalnum()
                            and not cmd[0].isdigit() and not cmd[1:2].isdigit()):
                        fehler.append(
                            f"{pfad}:{sek['zeile']}: Befehlsname '{cmd}' ist in Klipper ungueltig "
                            f"(\"Can't register ... invalid name\"): benannte Makros brauchen "
                            f"GROSSBUCHSTABEN + [A-Z0-9_] und Ziffern erst ab Stelle 3 "
                            f"(z.B. nicht R2_SELBSTTEST -> SELBSTTEST).")

    # ---- Choice-Pruefung bekannter Optionen (Klipper: "Choice ... not a valid choice") --
    CHOICES = {
        'screw_thread': ['CW-M3','CCW-M3','CW-M4','CCW-M4','CW-M5','CCW-M5','CW-M6','CCW-M6'],
    }
    for pfad in dateien:
        for sek in parse_cfg(pfad):
            for k in sek['keys']:
                if k['key'] in CHOICES:
                    w = k['wert'].strip().split('#')[0].strip().strip('\'"')
                    if w and w.upper() not in CHOICES[k['key']]:
                        fehler.append(f"{pfad}:{k['zeile']}: {k['key']}='{w}' invalid. "
                                      f"Erlaubt: {', '.join(CHOICES[k['key']])}")

    # ---- VALUE= muss Python-Literale sein (Klipper: ast.literal_eval!) ---------------
    # 'true'/'false' (klein, JSON/Marlin-Stil) sind KEINE Python-Literale -> Klipper:
    # "Unable to parse 'true' as a literal". Korrekt: True/False (gross) bzw. {bool}.
    import re as _re
    boese = [r'VALUE=true\b', r'VALUE=false\b', r"VALUE=\{[a-zA-Z_.]+\|lower\}", r"VALUE=\{'true'"]
    for pfad in dateien:
        for sek in parse_cfg(pfad):
            for k in sek['keys']:
                if k['key'] != 'gcode':
                    continue
                text = '\n'.join(k['block'])
                for pat in boese:
                    m = _re.search(pat, text)
                    if m:
                        fehler.append(f"{pfad}:{k['zeile']}: '{m.group(0)}' is not a Python literal! "
                                      f"SAVE_VARIABLE/SET_GCODE_VARIABLE parsen mit ast.literal_eval -> "
                                      f"Booleans GROSS schreiben (True/False), nicht true/false.")

    # ---- LCD safety: no non-ASCII characters in cfg files (12864 shows garbage) ------
    for pfad in dateien:
        for nr, zeile in enumerate(open(pfad, encoding='utf-8'), 1):
            try:
                zeile.encode('ascii')
            except UnicodeEncodeError:
                # R63 exception: variable_charset is DATA for the label text editor
                # (indexed, stored, printed) - it is never rendered 1:1 on the LCD
                if zeile.strip().startswith('variable_charset:'):
                    continue
                fehler.append(f"{pfad}:{nr}: non-ASCII character (LCD garbles it): {zeile.strip()[:60]}")

    # ---- shlex trap: VALUE='' / VALUE="" collapses to an EMPTY argument ---------------
    # Klipper parses extended gcode params with shlex(posix=True) -> the quotes are
    # shell quoting and get STRIPPED -> ast.literal_eval('') dies with
    # "Unable to parse '' as a literal". Empty string must be written VALUE='""'
    import re as _re2
    for pfad in dateien:
        for nr, zeile in enumerate(open(pfad, encoding='utf-8'), 1):
            if _re2.search(r"VALUE\s*=\s*(''|\"\")\s*$", zeile.rstrip()):
                fehler.append(f"{pfad}:{nr}: VALUE='' collapses to EMPTY after shlex "
                              f"(Klipper strips the quotes) - write VALUE='\"\"' instead: {zeile.strip()[:60]}")

    # ---- SAVE_VARIABLE/SET_GCODE_VARIABLE names must be lower case ---------------------
    # Klipper rejects upper case ("VARIABLE must not contain upper case"). Static
    # names are checked directly; DYNAMIC names (VARIABLE=prefix{jinja}) only pass
    # when the expression pipes through |lower (that was the pid_hotend_PLA bug).
    import re as _re3
    for pfad in dateien:
        for nr, zeile in enumerate(open(pfad, encoding='utf-8'), 1):
            for m2 in _re3.finditer(r'VARIABLE=([A-Za-z_0-9]+)', zeile):
                if m2.group(1) != m2.group(1).lower():
                    fehler.append(f"{pfad}:{nr}: VARIABLE name '{m2.group(1)}' contains UPPER CASE - "
                                  f"Klipper rejects it (must be lower case): {zeile.strip()[:60]}")
            for m2 in _re3.finditer(r'VARIABLE=([a-z_0-9]*)\{([^}]*)\}', zeile):
                if '|lower' not in m2.group(2):
                    fehler.append(f"{pfad}:{nr}: dynamic VARIABLE name '{{{m2.group(2)}}}' lacks '|lower' - "
                                  f"it could render UPPER CASE and Klipper would reject it: {zeile.strip()[:60]}")

    print(f"Files checked: {len(dateien)}")
    print(f"_STATE variables declared: {len(deklariert)}")
    print(f"SAVE_VARIABLE keys seen: {len(save_keys)}")
    if fehler:
        print(f"\n=== {len(fehler)} ERRORS ===")
        for f in fehler:
            print(" -", f)
        sys.exit(1)
    print("\nNo errors found.")

if __name__ == '__main__':
    main()
