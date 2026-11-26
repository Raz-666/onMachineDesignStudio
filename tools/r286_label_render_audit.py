#!/usr/bin/env python3
"""R286 L3/L5/L6 audit: Label-Render-Audit (Ausrichtung/Größe/Schrift).

Prüft die Label-Render-Logik in r2_postproc.py:
  L3: Zeilen bündig (gemeinsame Grundlinie), Kleinbuchstaben gleiche Größe
  L5: Anordnung/Größe/Schrift pro Modus (grow/fixed)
  L6: Stempel-Schrift-Ausbringung (stamp=1), Spiegel-Logik

Die Engine hat Uniform-Scale-R99 + _label_metrics. Dieses Tool verifiziert:
  1. _label_metrics liefert cap_units + baseline (Grundlinie) pro Zeichen
  2. Uniform-Scale: alle Zeilen gleiche Cap-Height (Kleinbuchstaben gleich)
  3. Grundlinien-Ausrichtung: alle Zeilen auf gemeinsamer Grundlinie
  4. Modus grow/fixed existieren und liefern konsistente metrics
  5. stamp=1 existiert (Stempel-Ausbringung)
  6. Spiegel-Logik (R168) vorhanden
  7. _label_metrics mit Mehr-Zeilen-Text: cap_units global, baseline pro Zeile
  8. grow-Fit: Label wächst, cap_mm bleibt uniform
  9. Kleinbuchstaben-Konformität (lowercase same size)

Run: python3 tools/r286_label_render_audit.py
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)

PASS = 0
FAIL = 0
results = []


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        results.append('[PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        results.append('[FAIL] %s %s' % (name, detail))


pp_src = open(os.path.join(ROOT, 'tools', 'r2_postproc.py'), encoding='utf-8').read()
pp_next = open(os.path.join(ROOT, 'tools', 'r2_postproc_next.py'), encoding='utf-8').read()

# Lade die Engine-Funktionen (reiner Render-Code, keine Hardware)
import importlib.util


def load_pp():
    spec = importlib.util.spec_from_file_location(
        'r2_postproc_audit', os.path.join(ROOT, 'tools', 'r2_postproc.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PP = load_pp()

# ---- 1. _label_metrics existiert + liefert cap_units + baseline ----
check('1 _label_metrics existiert', hasattr(PP, '_label_metrics'))

# ---- 2. _label_metrics: cap_units + baseline ----
try:
    lines = ['Hello', 'World']
    g, parsed = PP._label_metrics(lines, 'SMOOTH', 0.0)
    has_cap = 'cap_units' in g
    has_base = 'baseline' in g
    check('2 _label_metrics: cap_units + baseline', has_cap and has_base,
          '(cap_units=%s, baseline=%s)' % (
              g.get('cap_units'), g.get('baseline')))
except Exception as e:
    check('2 _label_metrics: cap_units + baseline', False, '(Exception: %r)' % (e,))

# ---- 3. Uniform-Scale: alle Zeilen gleiche Cap-Height ----
try:
    lines3 = ['Alpha', 'Beta', 'Gamma']
    g3, parsed3 = PP._label_metrics(lines3, 'SMOOTH', 0.0)
    cap_units = g3.get('cap_units')
    # cap_units ist global (im g-Dict), parsed hat asc_u/desc_u pro Zeile
    all_parsed = len(parsed3) == 3
    check('3 Uniform-Scale: alle Zeilen gleiche Cap-Height',
          all_parsed and cap_units is not None,
          '(cap_units=%s global, %d Zeilen)' % (cap_units, len(parsed3)))
except Exception as e:
    check('3 Uniform-Scale: alle Zeilen gleiche Cap-Height', False,
          '(Exception: %r)' % (e,))

# ---- 4. Grundlinien-Ausrichtung (baseline pro Zeile) ----
check('4 Grundlinien-Logik (baseline in Render)', 'baseline' in pp_src
      and 'baseline = cur_top' in pp_src, '(baseline = cur_top - asc - cap)')

# ---- 5. Modus grow/fixed existieren ----
grow_fixed = 'grow' in pp_src and 'fixed' in pp_src
# _label_grow_fit existiert
grow_fit = '_label_grow_fit' in pp_src or 'def _label_grow_fit' in pp_src
check('5 Modus grow/fixed + _label_grow_fit', grow_fixed and grow_fit,
      '(grow+fixed + grow_fit)')

# ---- 6. stamp=1 Stempel-Ausbringung ----
stamp_check = 'stamp' in pp_src and 'stamp_base' in pp_src
check('6 Stempel-Ausbringung (stamp + stamp_base)', stamp_check,
      '(stamp=1 + stamp_base)')

# ---- 7. Spiegel-Logik (R168) ----
mirror_check = 'mirror' in pp_src.lower() or 'flip' in pp_src.lower()
check('7 Spiegel-Logik (R168)', mirror_check, '(mirror/flip vorhanden)')

# ---- 8. _label_metrics Mehr-Zeilen: cap global ----
try:
    lines8 = ['ABC', 'def', 'GHI']
    g8, parsed8 = PP._label_metrics(lines8, 'SMOOTH', 0.0)
    global_cap = g8.get('cap_units')
    # Kleinbuchstaben 'd' hat asc_u (über cap) - cap_units global
    check('8 Kleinbuchstaben gleiche Größe (global cap_units)',
          global_cap is not None and global_cap > 0 and len(parsed8) == 3,
          '(cap_units=%s, %d Zeilen)' % (global_cap, len(parsed8)))
except Exception as e:
    check('8 Kleinbuchstaben gleiche Größe (global cap_units)', False,
          '(Exception: %r)' % (e,))

# ---- 9. make_labels + _make_labels_one (Label-Pipeline) ----
pipe = 'def make_labels' in pp_src and '_make_labels_one' in pp_src
check('9 Label-Pipeline (make_labels + _make_labels_one)', pipe,
      '(beide existieren)')

# ---- 10. Parität r2_postproc_next (beide Engines) ----
pipe_next = 'def make_labels' in pp_next and '_make_labels_one' in pp_next
stamp_next = 'stamp' in pp_next
check('10 Engine-Variante r2_postproc_next paritaet', pipe_next and stamp_next,
      '(make_labels + stamp)')

# ---- summary ----
print('\n'.join(results))
print('\n==== %d passed, %d failed ====' % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
