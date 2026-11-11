"""R246d (.142c): ONE source of truth for the release version - read from
the macro package itself, never typed into a document by hand.

WHY: every generated PDF carried its own hard-coded stamp
('R2-2026-11-09.136ai' in five builders, 'R2-2026-11-09.138' in two more).
After four releases the documents still claimed .136ai - the staleness was
invisible because nobody diffs a PDF. The version now comes from
macros/01_state.cfg (variable_version), the same string the LCD shows and
r199_zip_check.py verifies. A document can no longer be older than the
code it documents.

Usage:
    from r2_version import VERSION          # 'R2-2026-11-11.142c'
    from r2_version import VERSION_SHORT    # '.142c'
    from r2_version import BUILD            # 'R246d'
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_STATE = os.path.join(_ROOT, 'macros', '01_state.cfg')


def _read_version():
    try:
        with open(_STATE, encoding='utf-8') as f:
            m = re.search(r"variable_version:\s*'([^']+)'", f.read())
        if m:
            return m.group(1)
    except OSError:
        pass
    return 'unknown'


VERSION = _read_version()
# '.142c' out of 'R2-2026-11-11.142c' (what the menus and badges show)
VERSION_SHORT = VERSION.rsplit('.', 1)[-1] if '.' in VERSION else VERSION
if not VERSION_SHORT.startswith('.'):
    VERSION_SHORT = '.' + VERSION_SHORT

# the build tag the post-processor reports ('R246d')
POSTPROC = os.path.join(_HERE, 'r2_postproc.py')
BUILD = 'unknown'
try:
    with open(POSTPROC, encoding='utf-8') as f:
        _m = re.search(r"POSTPROC_BUILD\s*=\s*'([^']+)'", f.read())
    if _m:
        BUILD = _m.group(1)
except OSError:
    pass


if __name__ == '__main__':
    print('VERSION       %s' % VERSION)
    print('VERSION_SHORT %s' % VERSION_SHORT)
    print('BUILD         %s' % BUILD)
