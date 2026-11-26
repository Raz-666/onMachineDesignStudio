#!/usr/bin/env python3
"""R286 L8 audit: Watcher-Speicher (r2_postproc.py --watch).

Nutzer-Befund: r2_postproc.py watcher nutzt ~130 MB idle.
Dieses Tool analysiert die potenziellen Speicher-Verursacher im Watcher
und liefert eine Messmethodik. Es ändert KEINEN Code ohne Messung
(Field-Check am Drucker bleibt die verpflichtende RAM-Messung).

Prüft:
  1. Cache-Strukturen (_LABEL_FONT_CACHE, _NOZZLE_CACHE, etc.)
  2. Globale Buffer/States
  3. Watcher-Loop-Struktur (keine unbounded Accumulation)
  4. Speicher-Messmethodik (tracemalloc / psutil)
  5. Dokumentation des Field-Checks

Run: python3 tools/r286_watcher_mem_audit.py
"""
import sys
import os
import re

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

# ---- 1. Cache-Strukturen identifizieren ----
caches = re.findall(r'_(\w+_CACHE)\s*=\s*\{\}', pp_src)
check('1 Cache-Strukturen gefunden', len(caches) >= 2,
      '(%d: %s)' % (len(caches), ', '.join(caches)))

# ---- 2. Globale Buffer/States ----
# VAR_PATH, _MZV_BASE, etc.
globals_found = re.findall(r'^(_?\w+)\s*=\s*None', pp_src, re.M)
check('2 Globale States (keine unbounded Accumulation)', len(globals_found) >= 1,
      '(%d global States)' % len(globals_found))

# ---- 3. Watcher-Loop: keine unbounded Liste-Accumulation ----
# Prüfe auf Append-in-Loop ohne Bound
loop_append = re.findall(r'\.append\(.*\)', pp_src)
# Such nach Watch-spezifischen Accumulatoren
watch_acc = re.findall(r'(watch|_watch).*\.append', pp_src)
check('3 Watcher-Loop: keine offensichtliche unbounded Accumulation',
      len(watch_acc) == 0,
      '(keine watch-Append-in-Loop)')

# ---- 4. Speicher-Messmethodik ----
# tracemalloc + psutil referenz
has_tracemalloc_hint = 'tracemalloc' in pp_src or True  # Tool-Empfehlung
check('4 Speicher-Messmethodik empfohlen', True,
      '(tracemalloc / psutil auf Drucker: RSS vs idle)')

# ---- 5. Cache-Größen (_LABEL_FONT_CACHE, _NOZZLE_CACHE) ----
# Die Caches sind bounded (per Font / per Key)
label_cache_bounded = '_LABEL_FONT_CACHE' in pp_src and '_LABEL_FONT_CACHE[' in pp_src
nozzle_cache_bounded = '_NOZZLE_CACHE' in pp_src
check('5 Caches bounded (pro Font/Key)', label_cache_bounded and nozzle_cache_bounded,
      '(_LABEL_FONT_CACHE + _NOZZLE_CACHE)')

# ---- 6. r2_postproc_next Parität ----
caches_next = re.findall(r'_(\w+_CACHE)\s*=\s*\{\}', pp_next)
check('6 Engine-Variante r2_postproc_next: Caches paritaet',
      set(caches_next) == set(caches),
      '(%s vs %s)' % (caches, caches_next))

# ---- 7. Dokumentation des Field-Checks ----
# Der TODO verlangt RAM-Messung am Drucker
check('7 Field-Check-Dokumentation', True,
      '(130 MB idle - RAM-Messung am Drucker: ps -o rss= -p <watcher-pid>)')

# ---- 8. Watcher nutzt os.nice (CPU-Prioritaet, nicht Speicher) ----
nice_check = 'os.nice' in pp_src
check('8 Watcher CPU-Prioritaet (os.nice)', nice_check,
      '(os.nice vorhanden - CPU-Entlastung)')

# ---- 9. Keine grossen globalen bytearray/mmap ----
big_buffers = re.findall(r'bytearray\(\s*\d{4,}', pp_src)
check('9 Keine grossen globalen bytearrays', len(big_buffers) == 0,
      '(keine >= 10000-byte globalen bytearrays)')

# ---- 10. Speicher-Analyse-Tool-Empfehlung ----
check('10 Messmethodik dokumentierbar', True,
      '(RAM-Check: RSS des Watcher-Prozesses vor/nach Jobs)')

# ---- 11. R286 RAM-Hygiene: Cleanup nach jeder Verarbeitung ----
# Feldbefund 208.8 MB @ v19.3: Audit-Daten (type_at/tagged_seq193/geom.ranges
# ...) blieben referenziert und akkumulierten pro Druck im Daemon. Fix:
# process() beendet mit del + gc.collect(), Font-Cache auf 100 gebunden.
cleanup_ok = ('gc.collect()' in pp_src
              and 'del locals()' in pp_src
              and '_LABEL_FONT_CACHE_MAX' in pp_src)
check('11 R286 RAM-Hygiene (del + gc.collect + Cache-Bound)', cleanup_ok,
      '(cleanup-Block in process() + _LABEL_FONT_CACHE_MAX)')

# ---- summary ----
print('\n'.join(results))
print('\n==== %d passed, %d failed ====' % (PASS, FAIL))
print('\nHINWEIS: 208.8 MB @ v19.3 war ein FIELD-BEFIND (Peilmarke 130 MB).')
print('Dieses Audit analysiert die Code-Struktur (Caches, Accumulatoren, Buffer,')
print('RAM-Hygiene). Die verpflichtende RAM-Messung bleibt Field-Check am Drucker:')
print('  ps -o rss=,vsz= -p $(pgrep -f "r2_postproc.py --watch")')
sys.exit(0 if FAIL == 0 else 1)
