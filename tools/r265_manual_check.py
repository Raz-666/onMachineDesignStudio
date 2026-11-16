#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r265 - MANUAL.md gegen den CODE prüfen (MASTER-TODO D1).

Kein Umbau, kein Fix: dieses Werkzeug LIEST und BERICHTET. Es prüft die
Dinge, die sich mechanisch prüfen lassen, und schweigt zu allem anderen —
eine Doku, die „ungefähr stimmt", ist genau das Problem, das D1 lösen soll.

Geprüft wird:
  A  Makro-Index (§25)      - jeder gelistete Name existiert? jeder Makro gelistet?
  B  Zahlen im Text          - „194 entries", „239 public", „20 tunes", Slots, Zeichen
  C  LCD-Pfade              - „Pre-Print > Features > ..." gegen menus/lcd_menues.cfg
  D  Variablennamen          - ov_*/f_*/zh_*/ovar gegen macros/01_state.cfg
  E  Befehle in Code-Blöcken - SET_*/_*/M* gegen Makros bzw. Klipper-Standard

Aufruf:  python3 tools/r265_manual_check.py [--streng]
Exit:    0 = keine Abweichung, 1 = Abweichungen gefunden (--streng: auch Hinweise)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, 'MANUAL.md')

# Klipper-Standardbefehle, die kein R2-Makro brauchen (bewusst unvollständig:
# nur was im Handbuch vorkommt)
KLIPPER_STD = set('''
G0 G1 G2 G3 G4 G10 G11 G17 G18 G19 G20 G21 G28 G90 G91 G92
M18 M20 M21 M22 M23 M24 M25 M26 M27 M30 M73 M82 M83 M84 M105 M112 M114
M115 M117 M119 M204 M220 M221 M400 M84 M851 M862 M900 M117 M291 M600
SET_GCODE_OFFSET SET_PRESSURE_ADVANCE SET_INPUT_SHAPER SET_FAN_SPEED
SET_VELOCITY_LIMIT SET_PRINT_STATS_INFO SET_HEATER_TEMPERATURE
BED_MESH_CALIBRATE BED_MESH_PROFILE BED_MESH_CLEAR BED_MESH_OUTPUT
PROBE PROBE_CALIBRATE PROBE_ACCURACY QUERY_PROBE Z_TILT_ADJUST
SCREWS_TILT_CALCULATE TESTZ ACCEPT ABORT SAVE_CONFIG RESTART FIRMWARE_RESTART
PAUSE RESUME CANCEL_PRINT CLEAR_PAUSE EMERGENCY_STOP STATUS
PID_CALIBRATE TUNING_TOWER MEASURE_AXES_NOISE SHAPER_CALIBRATE
EXCLUDE_OBJECT EXCLUDE_OBJECT_DEFINE EXCLUDE_OBJECT_START EXCLUDE_OBJECT_END
SDCARD_PRINT_FILE SDCARD_RESET_FILE M23 M24 M25 UPDATE_DELAYED_GCODE
SET_LED SET_LED_TEMPLATE RESPOND SET_DISPLAY_TEXT M118 MESH_PROBE_TEST
LOAD_BED_MESH UNLOAD_BED_MESH SAVE_VARIABLE M99106 M99204 M99220 M99221
M99300 M99104 M99109 M99140 M99190 M99112
'''.split())

HINWEISE, FEHLER = [], []


def lies(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


def makros():
    """Name -> Datei für jedes [gcode_macro]/[delayed_gcode] im Repo."""
    out = {}
    for d in ('macros', 'menus'):
        v = os.path.join(ROOT, d)
        if not os.path.isdir(v):
            continue
        for f in sorted(os.listdir(v)):
            if not f.endswith('.cfg'):
                continue
            for m in re.finditer(r'^\[(?:gcode_macro|delayed_gcode) ([^\]]+)\]',
                                 lies(os.path.join(v, f)), re.M):
                out[m.group(1).strip()] = '%s/%s' % (d, f)
    return out


def menue_pfade():
    """Menge aller existierenden Menüzweige als Tupel von Namen."""
    txt = lies(os.path.join(ROOT, 'menus', 'lcd_menues.cfg'))
    pfade = set()
    for m in re.finditer(r'^\[menu ([^\]]+)\]', txt, re.M):
        pfade.add(tuple(m.group(1).split()))
    return pfade


def state_variablen():
    txt = lies(os.path.join(ROOT, 'macros', '01_state.cfg'))
    vs = set(re.findall(r'^variable_([a-zA-Z0-9_]+):', txt, re.M))
    for f in os.listdir(os.path.join(ROOT, 'macros')):
        if f.endswith('.cfg'):
            vs |= set(re.findall(r'variable_([a-zA-Z0-9_]+):',
                                 lies(os.path.join(ROOT, 'macros', f)), re.M))
    sv = lies(os.path.join(ROOT, 'macros', '01_state.cfg'))
    vs |= set(re.findall(r'SAVE_VARIABLE VARIABLE=([a-zA-Z0-9_]+)', sv))
    return vs


# --------------------------------------------------------------------- A
def pruefe_index(man, mks):
    """§25: gelistete Makros müssen existieren, existierende gelistet sein."""
    i = man.find('## 25. Complete macro index')
    j = man.find('## 26.', i)
    teil = man[i:j if j > 0 else len(man)]
    gelistet = set()
    for zeile in teil.split('\n'):
        if not zeile.startswith('|'):
            continue
        zellen = [z.strip() for z in zeile.strip('|').split('|')]
        if not zellen:
            continue
        name = zellen[0].replace('**', '').strip()
        if not name or name in ('Macro', '---') or name.startswith('-'):
            continue
        for n in re.split(r'\s*/\s*', name):
            n = n.strip()
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', n or ''):
                gelistet.add(n)
    fehlt_im_code = sorted(n for n in gelistet if n not in mks)
    # interne Helfer sind laut Kopfzeile bewusst nicht alle gelistet
    nicht_gelistet = sorted(n for n in mks
                            if n not in gelistet and not n.startswith('_'))
    intern_nicht = sorted(n for n in mks
                          if n not in gelistet and n.startswith('_'))
    for n in fehlt_im_code:
        FEHLER.append('A: Index nennt **%s**, im Code gibt es kein solches Makro' % n)
    oeffentlich = [n for n in mks if not n.startswith('_')]
    intern = [n for n in mks if n.startswith('_')]
    if len(nicht_gelistet) > 20:
        HINWEISE.append('A: %d öffentliche Makros sind NICHT im Index (z. B. %s)'
                        % (len(nicht_gelistet), ', '.join(nicht_gelistet[:8])))
    return {'gelistet': len(gelistet), 'code_publik': len(oeffentlich),
            'code_intern': len(intern), 'index_fehlt_code': fehlt_im_code,
            'code_fehlt_index': nicht_gelistet, 'intern_fehlt_index': intern_nicht}


# --------------------------------------------------------------------- B
def pruefe_zahlen(man, mks):
    """Zahlen, die im Text stehen und zählbar sind."""
    erg = {}
    # "194 entries" im Index-Kopf
    m = re.search(r'(\d+) entries: every public macro', man)
    if m:
        erg['index_entries_behauptet'] = int(m.group(1))
    m = re.search(r'(\d+) public \+ (\d+) internal macros exist', man)
    if m:
        erg['behauptet_public'] = int(m.group(1))
        erg['behauptet_intern'] = int(m.group(2))
    # Anzahl Klänge
    snd = lies(os.path.join(ROOT, 'macros', '02_sounds.cfg'))
    tunes = len(re.findall(r'^\s*"[a-z0-9_]+"\s*:', snd, re.M))
    if 'play all' in man.lower() and tunes:
        erg['klaenge_code'] = tunes
    # LED-Zustände = [led_effect r2_*] minus den Düsenlicht-Effekt
    led = lies(os.path.join(ROOT, 'macros', '03_leds.cfg'))
    eff = set(re.findall(r'^\[led_effect (r2_[a-z_]+)\]', led, re.M))
    erg['led_effects_code'] = len(eff)
    erg['led_states_code'] = len(eff - {'r2_nozzle_on'})
    st = re.search(r'\((\d+) states', man) or re.search(r'(\d+) states', man)
    if st:
        erg['led_states_behauptet'] = int(st.group(1))
        if int(st.group(1)) not in (erg['led_states_code'], erg['led_effects_code']):
            HINWEISE.append('B: Handbuch sagt %s LED-Zustände, Code hat %d '
                            '(%d inkl. Düsenlicht)'
                            % (st.group(1), erg['led_states_code'],
                               erg['led_effects_code']))
    # Makro-Zahlen im Index-Kopf
    pub = [n for n in mks if not n.startswith('_')]
    itn = [n for n in mks if n.startswith('_')]
    _txt = ''
    for _d in ('macros', 'menus'):
        _p = os.path.join(ROOT, _d)
        if os.path.isdir(_p):
            for _f in os.listdir(_p):
                if _f.endswith('.cfg'):
                    _txt += lies(os.path.join(_p, _f))
    _delayed = set(re.findall(r'^\[delayed_gcode ([^\]]+)\]', _txt, re.M))
    itn = [n for n in itn if n not in _delayed]      # Hooks zählen extra
    erg['code_publik'], erg['code_intern'] = len(pub), len(itn)
    erg['code_hooks'] = len(_delayed)
    if erg.get('behauptet_public') and erg['behauptet_public'] != len(pub):
        HINWEISE.append('B: Handbuch sagt „%d public", Code hat %d'
                        % (erg['behauptet_public'], len(pub)))
    if erg.get('behauptet_intern') and erg['behauptet_intern'] != len(itn):
        HINWEISE.append('B: Handbuch sagt „%d internal", Code hat %d'
                        % (erg['behauptet_intern'], len(itn)))
    return erg


# --------------------------------------------------------------------- C
def menue_labels():
    """Anzeigenamen der Menüpunkte: aus jeder [menu ...]-Sektion die name:-Zeile.

    Das Handbuch nennt Menüpunkte mit ihrem ANZEIGENAMEN („File info",
    „Profiles"), der Code mit dem Schlüssel (__file, __profs). Beides muss
    als gültig gelten, sonst produziert der Prüfer nur Rauschen.
    """
    txt = lies(os.path.join(ROOT, 'menus', 'lcd_menues.cfg'))
    labels = set()
    for blk in re.split(r'\n(?=\[menu )', txt):
        mm = re.match(r'\[menu ([^\]]+)\]', blk)
        if not mm:
            continue
        nm = re.search(r'^name: (.*)$', blk, re.M)
        if nm:
            roh = re.sub(r'\{[^}]*\}', '', nm.group(1))
            roh = roh.strip().strip("'\"").split(':')[0]
            roh = roh.split('(')[0]
            for teil in re.split(r'\s{2,}|/|\|', roh):
                teil = teil.strip(' .+-')
                if 2 <= len(teil) <= 26:
                    labels.add(teil)
        labels.add(mm.group(1).split()[-1])
    return {l.lower().replace('-', ' ').replace('_', ' ').strip() for l in labels}


def pruefe_menuepfade(man, pfade):
    """Prüft (Obermenü, erster Unterzweig) — dort sitzen die Doku-Fehler.

    Bewusst NICHT geprüft: tiefere Ebenen und Prosa. Ein Prüfer, der
    „ON + value > 0" für einen Menüpfad hält, ist schlimmer als keiner.
    """
    labels = menue_labels()
    tops = {p[0].replace('__', '').replace('_', ' '): p[0] for p in pfade if len(p) == 1}
    alias = {'pre-print': '__preprint', 'pre print': '__preprint',
             'live tuning': '__live', 'live': '__live',
             'maintenance': '__maint', 'system': '__system',
             'start print': '__start', 'quick macros': '__macros',
             'sd card': '__sdcard', 'control': 'control', 'tools': '__mods'}
    treffer, offen = 0, []
    for m in re.finditer(r'\b([A-Z][A-Za-z \-]{2,20})\s*(?:&gt;|>)\s*'
                         r'([A-Za-z][A-Za-z0-9 .+\-]{1,24})', man):
        top = m.group(1).strip().lower()
        kind = m.group(2).strip().rstrip('.').strip()
        if top not in tops and top not in alias:
            continue
        if not re.fullmatch(r'[A-Za-z0-9 .+\-]+', kind) or len(kind.split()) > 3:
            continue
        treffer += 1
        k = kind.lower().replace('-', ' ').replace('_', ' ').strip()
        if k in labels:
            continue
        offen.append('%s > %s' % (m.group(1).strip(), kind))
    for o in sorted(set(offen))[:40]:
        HINWEISE.append('C: Menüzweig nicht auflösbar: %s' % o)
    return {'paare_geprueft': treffer, 'offen': len(set(offen))}


# --------------------------------------------------------------------- D
def pruefe_variablen(man, vs):
    kandidaten = set(re.findall(r'`\b((?:ov|ovf|f|zh|sv|opt)_[a-z0-9_]+)\b`', man))
    kandidaten |= set(re.findall(r'\b((?:ovf)_[a-z0-9_]+_[a-z]{2,4})\b', man))
    fehlt = sorted(c for c in kandidaten
                   if c not in vs and c.replace('ovf_', 'ov_') not in vs)
    for c in fehlt[:25]:
        HINWEISE.append('D: Variable %s steht im Handbuch, nicht im Code' % c)
    return {'geprueft': len(kandidaten), 'fehlt': fehlt}


# --------------------------------------------------------------------- E
def pruefe_befehle(man, mks):
    """Befehle in ```-Blöcken: müssen Makro oder Klipper-Standard sein."""
    bloecke = re.findall(r'```[a-z]*\n(.*?)```', man, re.S)
    offen = {}
    for b in bloecke:
        for zeile in b.split('\n'):
            z = zeile.strip()
            if not z or z.startswith(('#', ';', '>')):
                continue
            m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)(\s+(.*))?$', z)
            if not m:
                continue
            name, rest = m.group(1), (m.group(3) or '').strip()
            if name in mks or name in KLIPPER_STD:
                continue
            # nur echte Aufrufe: nichts dahinter, oder PARAM= / Zahl / -Zahl
            if rest and not (re.match(r'^[A-Z_]+=', rest)
                             or re.match(r'^-?[0-9.]', rest)
                             or re.match(r'^[A-Z_]+\s', rest)):
                continue
            if '[' in z or '(' in z or '  ' in z:
                continue
            if name.isupper() or name.startswith('_'):
                offen[name] = z[:70]
    for n, z in sorted(offen.items()):
        HINWEISE.append('E: Befehl %s unbekannt (weder Makro noch Klipper-Standard): %s'
                        % (n, z))
    return {'bloecke': len(bloecke), 'unbekannt': sorted(offen)}


def main():
    if not os.path.isfile(MAN):
        print('[ERROR] MANUAL.md fehlt')
        return 1
    man = lies(MAN)
    mks = makros()
    pfade = menue_pfade()
    vs = state_variablen()

    r = {}
    r['A'] = pruefe_index(man, mks)
    r['B'] = pruefe_zahlen(man, mks)
    r['C'] = pruefe_menuepfade(man, pfade)
    r['D'] = pruefe_variablen(man, vs)
    r['E'] = pruefe_befehl = pruefe_befehle(man, mks)

    print('MANUAL.md <> CODE  (%d Zeilen, %d Makros im Code, %d Menüzweige)'
          % (man.count('\n'), len(mks), len(pfade)))
    print()
    a = r['A']
    print('A  Makro-Index: %d Namen gelistet · Code: %d öffentlich, %d intern'
          % (a['gelistet'], a['code_publik'], a['code_intern']))
    print('   gelistet, aber nicht im Code: %s'
          % (', '.join(a['index_fehlt_code']) or '—'))
    print('   im Code, nicht gelistet: %d öffentliche (%s …)'
          % (len(a['code_fehlt_index']), ', '.join(a['code_fehlt_index'][:6]) or '—'))
    b = r['B']
    print('B  Zahlen: %s' % b)
    c = r['C']
    print('C  Menüpfade: %d Paare geprüft, %d nicht auflösbar'
          % (c['paare_geprueft'], c['offen']))
    d = r['D']
    print('D  Variablen: %d geprüft, %d fehlen im Code'
          % (d['geprueft'], len(d['fehlt'])))
    e = r['E']
    print('E  Befehle: %d Code-Blöcke, %d unbekannte Befehle'
          % (e['bloecke'], len(e['unbekannt'])))
    print()
    if FEHLER:
        print('FEHLER (%d):' % len(FEHLER))
        for f in FEHLER:
            print('  -', f)
    if HINWEISE:
        print('HINWEISE (%d):' % len(HINWEISE))
        for h in HINWEISE:
            print('  -', h)
    if not FEHLER and not HINWEISE:
        print('keine Abweichung gefunden')
    return 1 if (FEHLER or ('--streng' in sys.argv and HINWEISE)) else 0


if __name__ == '__main__':
    sys.exit(main())
