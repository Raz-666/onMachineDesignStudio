"""R286: Verifikation der Label-Zeichensatz-Sanitisierung (kyrillische/
nicht-unterstuetzte Zeichen).

Befund: ein kyrillisches 'T' (U+0422, Homoglyph des lateinischen 'T')
gelangte ungestuuerd in den Render-G-Code eines gemischten Label
('Mix A~Тест B' -> kyrillische Zeichen im G-Code). Vollständig kyrillische
Labels warfen nur in einer Datei-Lese-Funktion einen sauberen Error, der
make_labels-Pfad sanitisierte nicht.

Fix: Zeichen ausserhalb LABEL_CHARSET werden zu '?' ersetzt (in
label_preview + _make_labels_one, beide Engines), konsistent mit der
Datei-Lese-Sanitisierung. Deutsche/englische Labels bleiben unversehrt.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from tools.r2_postproc import make_labels, LABEL_CHARSET


def _has_cyrillic(s):
    return any(0x0400 <= ord(c) <= 0x052F for c in s)


def main():
    tmp = tempfile.mkdtemp(prefix='r286_cyr_')
    ok = True

    # 1) Gemischte Labels: kyrillische Zeichen SANITIERSEN, kein Crash,
    #    kein kyrillischer Text im G-Code.
    mixed = ['Mix A~Тест B', 'OK~Тест', 'Layer~Привет']
    for txt in mixed:
        path, _ = make_labels([txt], w=120, h=60, out_dir=tmp)
        gtxt = open(path).read()
        if _has_cyrillic(gtxt):
            print(f"FAIL {txt!r}: kyrillische Zeichen im G-Code")
            ok = False
        else:
            print(f"OK  {txt!r}: kyrillische Zeichen sanitisiert, G-Code sauber")

    # 2) Deutsche/englische Labels mit Umlauten bleiben unversehrt.
    german = ['Guten Tag', 'R2-D2', 'ÄÖÜ äöü', 'Schnelltest']
    for txt in german:
        path, _ = make_labels([txt], w=120, h=60, out_dir=tmp)
        gtxt = open(path).read()
        # Alle nicht-Erlaubten Zeichen (außer G-Code-Syntax) dürfen nicht vorkommen
        bad = set(c for c in gtxt
                  if ord(c) > 127 and c not in 'ÄÖÜäöüß°')
        if bad:
            print(f"FAIL {txt!r}: ungestuuerde Zeichen im G-Code: {bad}")
            ok = False
        else:
            print(f"OK  {txt!r}: deutsche Label unversehrt")

    # 3) LABEL_CHARSET selbst ist kyrillisch-frei.
    if any(0x0400 <= ord(c) <= 0x052F for c in LABEL_CHARSET):
        print("FAIL: LABEL_CHARSET enthaelt kyrillische Zeichen")
        ok = False
    else:
        print(f"OK  LABEL_CHARSET kyrillisch-frei ({len(LABEL_CHARSET)} Zeichen)")

    print('\nErgebnis:', 'ALLE CHECKS PASSED' if ok else 'FEHLER')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
