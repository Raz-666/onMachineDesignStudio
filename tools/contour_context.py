"""Conservative metadata provenance, not geometric object/feature inference."""
from collections import Counter
import shlex

HELPER_HINTS = frozenset(('brim', 'skirt', 'skirt/brim', 'support', 'support interface',
                          'support material', 'support material interface',
                          'raft', 'prime tower', 'wipe tower', 'purge tower',
                          'ironing', 'custom'))
OUTER_HINTS = frozenset(('outer wall', 'external perimeter', 'wall-outer'))


def feature_role(hint):
    text = (hint or '').strip().lower()
    if text in HELPER_HINTS:
        return 'helper_hint_excluded'
    if text in OUTER_HINTS:
        return 'outer_wall_hint_unverified'
    return 'unclassified'


class ObjectContext:
    """Track explicit START/END names. Names are file-local, not global IDs.

    No DEFINE polygon is treated as geometry. This parser never makes a command
    passive in Shadow. Missing/malformed/overlapping markers invalidate membership.
    """
    def __init__(self):
        self.name = None
        self.start_line = None
        self.diagnostics = Counter()

    def clear(self):
        self.name = self.start_line = None

    def consume(self, record):
        raw = record.get('raw', '').split(';',1)[0].strip()
        command = raw.split(None,1)[0].upper() if raw else ''
        if command not in ('EXCLUDE_OBJECT_START','EXCLUDE_OBJECT_END'):
            if record['kind'] == 'unknown':
                self.clear()
            return False
        try:
            fields = shlex.split(raw)[1:]
            if any(not f.startswith('NAME=') for f in fields) or len(fields) > 1:
                raise ValueError('unsupported fields')
            name = fields[0][5:] if fields else None
            if name is not None and (not name or len(name)>256 or any(ord(c)<32 for c in name)):
                raise ValueError('invalid name')
            if command.endswith('START'):
                if name is None or self.name is not None:
                    raise ValueError('missing name or overlapping start')
                self.name, self.start_line = name, record['line']
            else:
                if self.name is None or (name is not None and name != self.name):
                    raise ValueError('unmatched end')
                self.clear()
        except ValueError:
            self.diagnostics['invalid_object_markers'] += 1
            self.clear()
        return True

    def snapshot(self):
        return dict(name=self.name, start_line=self.start_line,
                    scope='source-file-local marker', verified_geometry=False)
