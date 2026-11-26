#!/usr/bin/env python3
"""R286 L1: Audit-Tool fur die Audio-Ausgangs-Quelle (Install/Update-Dialog).

L1 verlangt: Install/Update soll WAHLEN - Beep (Board-Piezo/MCU, M300) ODER
Klinke/HDMI (Raspberry-Host, umgeht die MCU). Die Auswahl wird in
save_variables.audio_source gespeichert; dieses Tool verifiziert:

  1. das Makro SET_AUDIO_SOURCE existiert, speichert audio_source und
     akzeptiert die drei Quellen (Validierungs-Tupel)
  2. das Default-Wert audio_source='beep' im Init-Pfad gesetzt wird
  3. M300 den Guard hat (host-Pfad bei klinke/hdmi, SET_PIN nur im beep-Zweig)
  4. der LCD-Dialog im Systemmenue existiert (menu __main __system __audiosrc)
  5. das save_variables-Key audio_source in der Variable-Init-Liste steht

Auftrag: Exit 0 = alles OK, Exit 1 = Fehler.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def strip_comments(body):
    """Entfernt Zeilen, die nur aus einem Comment beginnen (#)."""
    out = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith('#'):
            continue
        out.append(line)
    return '\n'.join(out)


def main():
    checks = []
    ok = True

    sounds = read('macros/02_sounds.cfg')
    state = read('macros/01_state.cfg')
    menus = read('menus/lcd_menues.cfg')

    # 1) SET_AUDIO_SOURCE-Makro: existiert, speichert, akzeptiert 3 Quellen
    m = re.search(r'\[gcode_macro SET_AUDIO_SOURCE\](.*?)(?=\n\[gcode_macro|\Z)',
                  sounds, re.S)
    if m and 'SAVE_VARIABLE VARIABLE=audio_source' in m.group(1):
        # die drei Quellen via Validierungs-Tupel "src not in ('beep','klinke','hdmi')"
        srcs = set(re.findall(r"'(beep|klinke|hdmi)'", m.group(1)))
        checks.append(('SET_AUDIO_SOURCE-Makro: existiert + speichert + 3 Quellen',
                       bool(m) and {'beep', 'klinke', 'hdmi'} <= srcs,
                       'Quellen im Tupel: %s' % sorted(srcs)))
    else:
        ok = False
        checks.append(('SET_AUDIO_SOURCE-Makro: existiert + speichert + 3 Quellen',
                       False, 'Makro fehlt oder speichert nicht audio_source'))

    # 2) Default audio_source='beep' im Init
    has_default = re.search(
        r"SAVE_VARIABLE VARIABLE=audio_source VALUE='beep'", state) is not None
    checks.append(('Default audio_source=beep im Init-Pfad',
                   has_default,
                   'gefunden' if has_default else 'fehlt'))
    ok = ok and has_default

    # 3) M300-Guard: host-Pfad vor SET_PIN, Comment-Zeilen ausgeschlossen
    m300 = re.search(r'\[gcode_macro M300\](.*?)(?=\n\[gcode_macro|\Z)',
                     sounds, re.S)
    if m300:
        body = m300.group(1)
        gcode_body = body[body.find('gcode:'):] if 'gcode:' in body else body
        # Comment-Zeilen entfernen, damit der Comment-Eintrag 'klinke' nicht
        # den host-Branch vorgegeben wird
        clean = strip_comments(gcode_body)
        host_idx = clean.find('src in (')
        setpin_idx = clean.find('SET_PIN')
        host_branch = ("'klinke'" in clean and 'RESPOND' in clean)
        setpin_after_host = (host_idx != -1 and setpin_idx != -1
                             and setpin_idx > host_idx)
        checks.append(('M300-Guard: host-Pfad bei klinke/hdmi, SET_PIN nur im beep-Zweig',
                       host_branch and setpin_after_host,
                       'host-Branch=%s, SET_PIN nach host=%s' %
                       (host_branch, setpin_after_host)))
        ok = ok and host_branch and setpin_after_host
    else:
        ok = False
        checks.append(('M300-Guard', False, 'M300-Makro fehlt'))

    # 4) LCD-Dialog im Systemmenue
    has_dialog = '[menu __main __system __audiosrc]' in menus
    has_3 = all(x in menus for x in
                ['__audiosrc __beep', '__audiosrc __klinke', '__audiosrc __hdmi'])
    checks.append(('LCD-Audio-Auswahl-Dialog im Systemmenue (3 Quellen)',
                   has_dialog and has_3,
                   'Dialog=%s, 3-Quellen=%s' % (has_dialog, has_3)))
    ok = ok and has_dialog and has_3

    # 5) audio_source in der Variable-Init-Liste
    has_init_line = re.search(r'VARIABLE=audio_source', state) is not None
    checks.append(('audio_source in save_variables-Init-Liste',
                   has_init_line,
                   'gefunden' if has_init_line else 'fehlt'))
    ok = ok and has_init_line

    # Ausgabe
    print('R286 L1 Audio-Ausgangs-Audit')
    print('=' * 60)
    for name, passed, detail in checks:
        status = 'OK  ' if passed else 'FAIL'
        print('  [%s] %s' % (status, name))
        print('         %s' % detail)
    print('=' * 60)
    print('Ergebnis:', 'ALLE CHECKS PASSED' if ok else 'FEHLER')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
