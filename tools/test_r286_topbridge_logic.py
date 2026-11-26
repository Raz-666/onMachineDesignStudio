"""R286: Verifikation der User-Logik-Korrektur (Top/Bridge auf Sparse-Infill).

User-Analyse (2026-11-25): die pauschale Regel "kein Top auf Sparse-Infill
-> BRIDGE" ist NICHT korrekt. Richtig ist:
  - bei nur EINEM Folgeschicht kann Top folgen (nicht automatisch Bridge)
  - bei MEHREREN Schichten auf dünnes Infill kommen Bridge ODER
    solid-infill-Folgeschichten + Top / Top+Ironing
  - bei explizit einer Folgeschicht kann direkt Top bzw. Top+Ironing folgen

Befund: die Engine-Logik (audit_tag_geometry, R281-Support-Welt) enthält die
Korrektur bereits - Top und Bridge sind getrennte Pfade. Ein SURFACE-TOP auf
Sparse-Infill wird NIEMALS als BRIDGE klassifiziert (kein G5_UNANCHORED_BRIDGE),
und solid infill + Top + Ironing wird korrekt als support-getragen akzeptiert
(kein G3_IRONING_UNSUPPORTED). Es gibt keine pauschale "Sparse->Bridge"-Entscheidung.

Dieses Test file documentiert den Beweis.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from tools.r2_postproc import audit_tag_geometry


def _write(tmp, name, body):
    p = os.path.join(tmp, name)
    with open(p, 'w') as f:
        f.write(body)
    return p


def main():
    tmp = tempfile.mkdtemp(prefix='r286_topbr_')
    ok = True

    # Szenario A: Sparse-Infill-Schicht -> Folgeschicht mit explizitem TOP.
    # Erwartung: KEIN G5 (Top ist nicht Bridge), KEIN G4 (nicht wiederholte
    # Top-Kappe ohne Wand).
    p = _write(tmp, 'a.gcode', (
        'M83\nG90\n;LAYER_CHANGE\n;Z:0.2\nLAYER_MARK\n'
        ';TYPE:Sparse infill\nAPPLY_TYPE TYPE=INFILL-SPARSE\n'
        'G1 X0 Y0 E1\nG1 X100 Y0 E2\nG1 X100 Y100 E3\nG1 X0 Y100 E4\nG1 X0 Y0 E5\n'
        ';LAYER_CHANGE\n;Z:0.4\nLAYER_MARK\n'
        ';TYPE:Top surface\nAPPLY_TYPE TYPE=SURFACE-TOP\n'
        'G1 X0 Y0 E1\nG1 X100 Y0 E2\nG1 X100 Y100 E3\nG1 X0 Y100 E4\nG1 X0 Y0 E5\n'
    ))
    by = audit_tag_geometry(p, cell_mm=2.0, fil_dia=1.75)['by_code']
    if 'G5_UNANCHORED_BRIDGE' in by:
        print('FAIL A: Top auf Sparse-Infill wurde als BRIDGE klassifiziert')
        ok = False
    else:
        print('OK A: Top auf Sparse-Infill = Top (NICHT Bridge), keine G5-Konflikt')

    # Szenario B: solid-Folgeschicht + Top + Ironing (User: solid-infill-
    # Folgeschicht kann Top+Ironing tragen). Erwartung: kein G3_IRONING_UNSUPPORTED.
    p = _write(tmp, 'b.gcode', (
        'M83\nG90\n;LAYER_CHANGE\n;Z:0.2\nLAYER_MARK\n'
        ';TYPE:Solid infill\nAPPLY_TYPE TYPE=INFILL-SOLID\n'
        'G1 X0 Y0 E1\nG1 X100 Y0 E2\nG1 X100 Y100 E3\nG1 X0 Y100 E4\nG1 X0 Y0 E5\n'
        ';LAYER_CHANGE\n;Z:0.4\nLAYER_MARK\n'
        ';TYPE:Top surface\nAPPLY_TYPE TYPE=SURFACE-TOP\n'
        'G1 X0 Y0 E1\nG1 X100 Y0 E2\nG1 X100 Y100 E3\nG1 X0 Y100 E4\nG1 X0 Y0 E5\n'
        ';TYPE:Ironing\nAPPLY_TYPE TYPE=IRONING\n'
        'G1 X0 Y0 E1\nG1 X100 Y0 E2\n'
    ))
    by = audit_tag_geometry(p, cell_mm=2.0, fil_dia=1.75)['by_code']
    if 'G3_IRONING_UNSUPPORTED' in by:
        print('FAIL B: Ironing auf solid+Top wurde als unsupported gemeldet')
        ok = False
    else:
        print('OK B: solid+Top+Ironing = support-getragen, keine G3-Konflikt')

    # Szenario C: echte, ins Leere ragende Bridge (kein Support unterhalb)
    # in der MITTELschicht, mit zwei Move-Segmenten (wie der bestehende
    # G5-Test in test_shadow_analysis_audit_v2.py). Erwartung: G5 GEMELDET.
    p = _write(tmp, 'c.gcode', (
        'G21\nG90\nM83\n'
        ';LAYER_CHANGE\n;Z:0.20\n'
        ';TYPE:Solid infill\nAPPLY_TYPE TYPE=INFILL-SOLID\n'
        'G1 X0 Y0 E1\nG1 X100 Y0 E2\nG1 X100 Y100 E3\nG1 X0 Y100 E4\nG1 X0 Y0 E5\n'
        ';LAYER_CHANGE\n;Z:0.40\n'
        ';TYPE:Bridge\nAPPLY_TYPE TYPE=BRIDGE\n'
        'G0 X200 Y200 Z0.40 F6000\nG1 X300 Y200 E0.8 F1200\n'
        'G0 X200 Y202 Z0.40 F6000\nG1 X300 Y202 E0.8 F1200\n'
        ';LAYER_CHANGE\n;Z:0.60\n'
        ';TYPE:Solid infill\nAPPLY_TYPE TYPE=INFILL-SOLID\n'
        'G1 X0 Y0 E1\nG1 X100 Y0 E2\nG1 X100 Y100 E3\nG1 X0 Y100 E4\nG1 X0 Y0 E5\n'
    ))
    by = audit_tag_geometry(p, cell_mm=2.0, fil_dia=1.75)['by_code']
    if 'G5_UNANCHORED_BRIDGE' not in by:
        print('FAIL C: echte ins-Leere-Bridge wurde NICHT als G5 gemeldet')
        ok = False
    else:
        print('OK C: echte unverankerte Bridge = G5 gemeldet (Top != Bridge bewahrt)')

    print('\nErgebnis:', 'ALLE CHECKS PASSED' if ok else 'FEHLER')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
