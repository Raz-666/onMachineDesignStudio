"""File-local marker provenance never implies geometric model membership."""
import unittest
from contour_context import ObjectContext, feature_role
from path_evidence import PathEvidence
from r2_shadow import Shadow


class ContextTests(unittest.TestCase):
    def marker(self, context, text, line=1):
        context.consume(dict(raw=text,line=line,kind='klipper_passive'))

    def test_named_unnamed_end_and_repeated_object(self):
        c=ObjectContext()
        for end in ('EXCLUDE_OBJECT_END NAME=a','EXCLUDE_OBJECT_END'):
            self.marker(c,'EXCLUDE_OBJECT_START NAME=a',12)
            self.assertEqual(c.snapshot()['name'],'a')
            self.assertEqual(c.snapshot()['start_line'],12)
            self.marker(c,end)
            self.assertIsNone(c.name)
        self.assertEqual(c.diagnostics,{})

    def test_invalid_or_overlapping_markers_clear_membership(self):
        for bad in ('EXCLUDE_OBJECT_END NAME=b','EXCLUDE_OBJECT_START NAME=b',
                    'EXCLUDE_OBJECT_START NAME=a NAME=b', 'EXCLUDE_OBJECT_END BAD=1',
                    'EXCLUDE_OBJECT_START NAME="unterminated'):
            c=ObjectContext()
            self.marker(c,'EXCLUDE_OBJECT_START NAME=a')
            self.marker(c,bad)
            self.assertIsNone(c.name)
            self.assertEqual(c.diagnostics['invalid_object_markers'],1)

    def test_unknown_command_invalidates_membership(self):
        c=ObjectContext()
        self.marker(c,'EXCLUDE_OBJECT_START NAME=a')
        c.consume(dict(raw='MYSTERY',kind='unknown',line=2))
        self.assertIsNone(c.name)

    def test_roles_conservative(self):
        for hint in ('Brim','Support interface','WALL-OUTER','Outer wall',None,'mystery'):
            role=feature_role(hint)
            self.assertIn(role,('helper_hint_excluded','outer_wall_hint_unverified','unclassified'))
        self.assertEqual(feature_role('Brim'),'helper_hint_excluded')
        self.assertEqual(feature_role('Outer wall'),'outer_wall_hint_unverified')
        self.assertEqual(feature_role('Outer wall-ish'),'unclassified')

    def test_object_and_feature_do_not_leak_between_paths(self):
        state=Shadow(klipper_passive=True)
        paths=PathEvidence(seam_gap_mm=.1)
        text=('G21\nG90\nM83\nG0 X0 Y0 Z.2\n'
              'EXCLUDE_OBJECT_START NAME=a\n;TYPE:Brim\n'
              'G1 X1 E1\nG1 Y1 E1\nG1 X0 Y0 E1\n'
              'EXCLUDE_OBJECT_END NAME=a\nEXCLUDE_OBJECT_START NAME=b\n'
              'G1 X1 E1\nG1 Y1 E1\nG1 X0 Y0 E1\nEXCLUDE_OBJECT_END\n')
        for n,raw in enumerate(text.splitlines(),1):paths.consume(state.process(raw,n))
        paths.finish('eof')
        result=paths.report()
        a,b=result['seam_policy']['proposals']
        self.assertEqual(a['object_context']['name'],'a')
        self.assertEqual(a['feature_role'],'helper_hint_excluded')
        self.assertEqual(b['object_context']['name'],'b')
        self.assertIsNone(b['feature_hint'])
        self.assertEqual(b['feature_role'],'unclassified')
        self.assertFalse(a['export_ready'])
        self.assertFalse(b['object_context']['verified_geometry'])


if __name__ == '__main__': unittest.main(verbosity=2)
