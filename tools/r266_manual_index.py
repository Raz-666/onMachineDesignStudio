#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r266 - den Makro-Index (§25) von MANUAL.md aus dem CODE neu bauen.

MASTER-TODO D1: Der Index behauptete „194 entries … 239 public + 100
internal", der Code hat 265 öffentliche + 114 interne gcode_macros (dazu 30
delayed_gcode-Hooks). Dieses Werkzeug schreibt §25 neu — und zwar so, dass
nichts erfunden wird:

  * Name, Datei und Parameter kommen aus den .cfg-Dateien,
  * der Zweck-Text bleibt der, der schon im Handbuch stand (er ist Prosa und
    war richtig); nur für NEUE Einträge wird `description:` aus dem Code
    genommen, und wo es keine gibt, steht „—",
  * die Abschnitts-Überschriften tragen die echten Zählungen.

Alles außerhalb von §25 bleibt Byte für Byte unangetastet.

Aufruf:  python3 tools/r266_manual_index.py [--schreiben]
Ohne --schreiben wird nur berichtet, was sich ändern würde.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, 'MANUAL.md')

# Reihenfolge und Klartext-Überschrift je Makro-Datei (wie im Handbuch)
DATEIEN = [
    ('01_state.cfg', 'State & sentinels'),
    ('02_sounds.cfg', 'Sounds'),
    ('03_leds.cfg', 'LEDs'),
    ('04_notify.cfg', 'Notifications'),
    ('05_materials.cfg', 'Materials & profiles'),
    ('06_temp_controls.cfg', 'Temperatures'),
    ('07_start_confirm.cfg', 'Start confirm'),
    ('08_print_start_stop.cfg', 'Print start / stop'),
    ('09_pause_filament.cfg', 'Pause & filament'),
    ('10_live_tuning.cfg', 'Live tuning'),
    ('11_gantry_sync.cfg', 'Gantry sync'),
    ('12_maintenance.cfg', 'Maintenance'),
    ('13_system.cfg', 'System'),
    ('14_kamp.cfg', 'KAMP'),
    ('15_objects.cfg', 'Objects'),
    ('16_labels.cfg', 'Labels'),
    ('17_generator.cfg', 'Generators'),
    ('18_colorpic.cfg', 'ColorPic'),
    ('19_bricks.cfg', 'Bricks'),
    ('../menus/lcd_menues.cfg', 'Menu helpers (menus/lcd_menues.cfg)'),
]


def lies(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


def bloecke(pfad):
    """[(art, name, body)] in Dateireihenfolge."""
    txt = lies(pfad)
    out = []
    for m in re.finditer(r'^\[(gcode_macro|delayed_gcode) ([^\]\n]+)\]\n',
                         txt, re.M):
        start = m.end()
        nxt = re.search(r'^\[', txt[start:], re.M)
        body = txt[start:start + (nxt.start() if nxt else len(txt))]
        out.append((m.group(1), m.group(2).strip(), body))
    return out


def params_von(body):
    """Parameter aus params.X|default(Y) -> ['X=Y', 'Z'] (Reihenfolge des Auftretens)."""
    gesehen = []
    for m in re.finditer(r'params\.([A-Z][A-Z0-9_]*)(\s*\|\s*default\(([^)]*)\))?',
                         body):
        name, dflt = m.group(1), m.group(3)
        if name in [g.split('=')[0] for g in gesehen]:
            if dflt and '=' not in gesehen[[g.split('=')[0]
                                           for g in gesehen].index(name)]:
                gesehen[[g.split('=')[0] for g in gesehen].index(name)] = \
                    '%s=%s' % (name, dflt.strip())
            continue
        gesehen.append('%s=%s' % (name, dflt.strip()) if dflt else name)
    return ', '.join(gesehen)


def saeubere(t):
    """Entfernt Epochen-/Revisionsangaben aus Code-Beschreibungen.

    USER-REGEL (R185): MANUAL.md beschreibt NUR den aktuellen Stand - keine
    Klammern wie „(.135)" oder „(R167)". Der Code ist voll davon, weil dort
    die Historie stehen MUSS. Im Handbuch hat sie nichts zu suchen.
    """
    if not t:
        return t
    t = re.sub(r'\s*\([^)]*\bR\d{2,3}\b[^)]*\)', '', t)      # (… R167 …)
    t = re.sub(r'\s*\([^)]*\.\d{2,3}[a-d]?\b[^)]*\)', '', t)  # (… .135 …)
    t = re.sub(r'\bR\d{2,3}\b[\s:,-]*', '', t)                  # führendes R167
    t = re.sub(r'\b\.\d{2,3}[a-d]?\b', '', t)                   # nacktes .142d
    t = re.sub(r'\(\s*(internal|see below)\s*\)', '', t)         # leere Hülle
    t = re.sub(r'\s{2,}', ' ', t).strip(' -,:;')
    return t


def beschreibung_von(body):
    m = re.search(r'^description:\s*(.+)$', body, re.M)
    if not m:
        return ''
    t = m.group(1).strip()
    t = re.sub(r'\s*\((internal|R\d+[^)]*)\)\s*$', '', t)
    return saeubere(t.strip())


def zellen_aus_handbuch(teil):
    """{name: (params, purpose, datei_ueberschrift)} aus dem alten §25."""
    alt = {}
    ueberschrift = ''
    for zeile in teil.split('\n'):
        if zeile.startswith('### '):
            ueberschrift = zeile[4:].strip()
            continue
        if not zeile.startswith('|'):
            continue
        z = [c.strip() for c in zeile.strip('|').split('|')]
        if len(z) < 3 or z[0] in ('Macro', '---') or z[0].startswith('-'):
            continue
        name = z[0].replace('**', '').strip()
        for n in re.split(r'\s*/\s*', name):
            n = n.strip()
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', n or ''):
                alt[n] = (z[1], z[2], ueberschrift)
    return alt


def baue_index(trocken=True):
    man = lies(MAN)
    i = man.find('## 25. Complete macro index')
    j = man.find('## 26.', i)
    if i < 0 or j < 0:
        print('[ERROR] §25 nicht gefunden')
        return 1
    teil = man[i:j]
    alt = zellen_aus_handbuch(teil)

    neu = ['## 25. Complete macro index', '']
    eintraege = 0
    publik = intern = 0
    for datei, titel in DATEIEN:
        pfad = os.path.join(ROOT, 'macros', datei)
        if not os.path.isfile(pfad):
            continue
        bs = bloecke(pfad)
        gm = [(n, b) for a, n, b in bs if a == 'gcode_macro']
        if not gm:
            continue
        zeilen = []
        for name, body in sorted(gm, key=lambda x: (x[0].startswith('_'), x[0])):
            alt_p, alt_z, _u = alt.get(name, ('', '', ''))
            p = alt_p if alt_p and alt_p != '—' else params_von(body)
            z = (alt_z if alt_z and alt_z != '—'
                 else (beschreibung_von(body) or '—')).replace('|', '/')
            # IMMER säubern - auch die übernommenen Texte: ein zweiter Lauf
            # sieht die beim ersten Lauf erzeugten Texte als „alt" an, und
            # genau so schlichen sich die Revisionsklammern wieder ein.
            z = saeubere(z) or '—'
            fett = '**%s**' % name if not name.startswith('_') else name
            if name.startswith('_'):
                intern += 1
            else:
                publik += 1
            eintraege += 1
            zeilen.append('| %s | %s | %s |' % (fett, (p or '').replace('|', '/'), z))
        neu.append('### %s — %s (%d)' % (titel, datei, len(gm)))
        neu.append('| Macro | Parameters | Purpose |')
        neu.append('|---|---|---|')
        neu.extend(zeilen)
        neu.append('')
    # delayed_gcode-Hooks sammeln (die laufen nicht auf Zuruf, gehören aber rein)
    hooks = []
    for datei, _t in DATEIEN:
        pfad = os.path.join(ROOT, 'macros', datei)
        if not os.path.isfile(pfad):
            continue
        for art, name, body in bloecke(pfad):
            if art == 'delayed_gcode':
                intern += 1
                eintraege += 1
                hooks.append('| %s | — | %s |' % (name,
                                                  beschreibung_von(body)
                                                  or 'delayed_gcode hook (%s)' % datei))
    if hooks:
        neu.append('### delayed_gcode hooks (%d)' % len(hooks))
        neu.append('| Macro | Parameters | Purpose |')
        neu.append('|---|---|---|')
        neu.extend(hooks)
        neu.append('')

    kopf = ('%d entries: every public macro with parameters (defaults in '
            'parentheses; blank = no parameters) plus the internal hooks worth '
            'knowing. Internal helpers (leading `_`) are not user-facing — '
            '**%d public + %d internal macros exist in total** (%d `gcode_macro` '
            '+ %d `delayed_gcode`, counted from the .cfg files, not copied from '
            'an older list). Grouped by module file — the same file you would '
            'edit.'
            % (eintraege, publik, intern - len(hooks), publik + intern - len(hooks),
               len(hooks)))
    neu.insert(1, kopf)
    neu.insert(2, '')
    neuer_teil = '\n'.join(neu)

    print('§25 alt: %d Zeilen, %d gelistete Namen' % (teil.count('\n') + 1, len(alt)))
    print('§25 neu: %d Zeilen | %d Einträge | %d öffentlich, %d intern, %d Hooks'
          % (neuer_teil.count('\n') + 1, eintraege, publik, intern - len(hooks),
             len(hooks)))
    fehlend = sorted(set(alt) - {re.sub(r'\*\*', '', z.split('|')[1].strip())
                                 for z in neu if z.startswith('| ')
                                 for z in [z]})
    nachher = set()
    for z in neu:
        if z.startswith('| '):
            c = z.split('|')[1].strip().replace('**', '')
            for n in re.split(r'\s*/\s*', c):
                nachher.add(n.strip())
    wirklich_weg = sorted(n for n in alt if n not in nachher)
    print('Namen, die im alten Index standen und jetzt fehlen: %s'
          % (', '.join(wirklich_weg) or '—'))
    if not trocken:
        out = man[:i] + neuer_teil + man[j:]
        with open(MAN, 'w', encoding='utf-8') as f:
            f.write(out)
        print('MANUAL.md geschrieben')
    return 0


if __name__ == '__main__':
    sys.exit(baue_index(trocken='--schreiben' not in sys.argv))
