#!/usr/bin/env python3
"""Offline tests for the experimental image picker. Never contacts a printer."""
import ast
from concurrent.futures import ThreadPoolExecutor
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

if os.environ.get('R2_TEST_ENGINE') == 'active':
    import r2_postproc as pp
else:
    import r2_postproc_next as pp


class ImagePickTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='r2-image-pick-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sub').mkdir()
        (self.root / 'sub' / 'photo.png').write_bytes(b'nested image')

    def staging(self):
        return list(self.root.glob('.r2-img-*.tmp'))

    def test_new_destination_and_original_preserved(self):
        name, copied = pp._copy_picked_image(str(self.root), '/sub/photo.png')
        self.assertEqual(('photo.png', True), (name, copied))
        self.assertEqual(b'nested image', (self.root / name).read_bytes())
        self.assertEqual(b'nested image', (self.root / 'sub/photo.png').read_bytes())
        self.assertEqual([], self.staging())

    def test_collision_keeps_every_existing_file_and_reports_new_name(self):
        (self.root / 'photo.png').write_bytes(b'original')
        (self.root / 'photo_1.png').write_bytes(b'other')
        name, copied = pp._copy_picked_image(str(self.root), 'sub/photo.png')
        self.assertEqual(('photo_2.png', True), (name, copied))
        self.assertEqual(b'original', (self.root / 'photo.png').read_bytes())
        self.assertEqual(b'other', (self.root / 'photo_1.png').read_bytes())
        self.assertEqual(b'nested image', (self.root / name).read_bytes())
        self.assertEqual([], self.staging())

    def test_existing_root_pick_is_read_only_and_missing_root_fails(self):
        (self.root / 'root.JPG').write_bytes(b'root')
        before = (self.root / 'root.JPG').stat().st_mtime_ns
        self.assertEqual(('root.JPG', False), pp._copy_picked_image(str(self.root), '/root.JPG'))
        self.assertEqual(b'root', (self.root / 'root.JPG').read_bytes())
        self.assertEqual(before, (self.root / 'root.JPG').stat().st_mtime_ns)
        with self.assertRaises(FileNotFoundError):
            pp._copy_picked_image(str(self.root), 'not-present.jpg')
        self.assertEqual([], self.staging())

    def test_traversal_invalid_extension_and_command_injection_rejected(self):
        for name in ('', '../outside.png', 'sub/../photo.png', 'sub//photo.png',
                     'sub/./photo.png', 'sub/file.txt', 'sub/x;M112.png',
                     'sub/x\nM112.png', 'sub/x".png', "sub/x'.png", 'sub\\photo.png'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                pp._copy_picked_image(str(self.root), name)
        self.assertEqual([], self.staging())

    def test_symlink_sources_and_nested_symlink_directories_rejected(self):
        (self.root / 'sub' / 'link.png').symlink_to(self.root / 'sub/photo.png')
        (self.root / 'dirlink').symlink_to(self.root / 'sub', target_is_directory=True)
        for name in ('sub/link.png', 'dirlink/photo.png'):
            with self.subTest(name=name), self.assertRaises(OSError):
                pp._copy_picked_image(str(self.root), name)
        self.assertEqual([], self.staging())

    def test_existing_destination_symlink_not_followed_or_replaced(self):
        target = self.root / 'protected.txt'
        target.write_bytes(b'protected')
        (self.root / 'photo.png').symlink_to(target)
        name, copied = pp._copy_picked_image(str(self.root), 'sub/photo.png')
        self.assertEqual(('photo_1.png', True), (name, copied))
        self.assertTrue((self.root / 'photo.png').is_symlink())
        self.assertEqual(b'protected', target.read_bytes())
        self.assertEqual(b'nested image', (self.root / name).read_bytes())

    def test_directory_and_fifo_sources_are_refused_without_blocking(self):
        (self.root / 'sub' / 'directory.png').mkdir()
        os.mkfifo(self.root / 'sub' / 'fifo.png')
        for name in ('sub/directory.png', 'sub/fifo.png'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                pp._copy_picked_image(str(self.root), name)

    def test_copy_failure_keeps_original_and_leaves_no_partial_output(self):
        (self.root / 'photo.png').write_bytes(b'original')
        with mock.patch.object(pp.shutil, 'copyfileobj', side_effect=OSError(errno.ENOSPC, 'full')):
            with self.assertRaises(OSError):
                pp._copy_picked_image(str(self.root), 'sub/photo.png')
        self.assertEqual(b'original', (self.root / 'photo.png').read_bytes())
        self.assertFalse((self.root / 'photo_1.png').exists())
        self.assertEqual([], self.staging())

    def test_link_failure_keeps_original_and_cleans_staging(self):
        (self.root / 'photo.png').write_bytes(b'original')
        with mock.patch.object(pp.os, 'link', side_effect=OSError(errno.EOPNOTSUPP, 'unsupported')):
            with self.assertRaises(OSError):
                pp._copy_picked_image(str(self.root), 'sub/photo.png')
        self.assertEqual(b'original', (self.root / 'photo.png').read_bytes())
        self.assertEqual([], self.staging())

    def test_source_changed_mid_copy_is_not_published(self):
        copy = pp.shutil.copyfileobj
        def alter(src, dst, length):
            copy(src, dst, length)
            (self.root / 'sub/photo.png').write_bytes(b'changed and longer')
        with mock.patch.object(pp.shutil, 'copyfileobj', side_effect=alter):
            with self.assertRaisesRegex(OSError, 'changed while'):
                pp._copy_picked_image(str(self.root), 'sub/photo.png')
        self.assertFalse((self.root / 'photo.png').exists())
        self.assertEqual([], self.staging())

    def test_parallel_collision_is_atomic(self):
        (self.root / 'photo.png').write_bytes(b'original')
        for n in range(8):
            folder = self.root / ('src%d' % n)
            folder.mkdir()
            (folder / 'photo.png').write_bytes(('image%d' % n).encode())
        with ThreadPoolExecutor(max_workers=8) as pool:
            names = list(pool.map(lambda n: pp._copy_picked_image(
                str(self.root), 'src%d/photo.png' % n)[0], range(8)))
        self.assertEqual(8, len(set(names)))
        self.assertEqual(b'original', (self.root / 'photo.png').read_bytes())
        self.assertEqual({('image%d' % n).encode() for n in range(8)},
                         {(self.root / n).read_bytes() for n in names})
        self.assertEqual([], self.staging())

    def test_no_replace_mutation_is_caught(self):
        (self.root / 'photo.png').write_bytes(b'original')
        def destructive_link(src, dst, *, src_dir_fd, dst_dir_fd, follow_symlinks):
            os.replace(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
        with mock.patch.object(pp.os, 'link', side_effect=destructive_link):
            pp._copy_picked_image(str(self.root), 'sub/photo.png')
        # Proves the collision invariant above rejects an unsafe replacement.
        with self.assertRaises(AssertionError):
            self.assertEqual(b'original', (self.root / 'photo.png').read_bytes())

    def test_original_watcher_block_reports_actual_copy_and_error(self):
        source = Path(pp.__file__).read_text(encoding='utf-8')
        watch = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'watch')
        blocks = [n for n in ast.walk(watch) if isinstance(n, ast.Try) and n.body
                  and isinstance(n.body[0], ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == '_ipn' for t in n.body[0].targets)]
        self.assertEqual(1, len(blocks))
        code = compile(ast.fix_missing_locations(ast.Module(body=blocks, type_ignores=[])),
                       'r2_postproc_next.py', 'exec')
        (self.root / 'photo.png').write_bytes(b'original')
        notices = []
        env = {'rv': {'img_pick_nonce': '1', 'img_pick_file': 'sub/photo.png'},
               'last_img_pick_nonce': None, 'directory': str(self.root),
               '_copy_picked_image': pp._copy_picked_image, '_moonraker_gcode': notices.append}
        exec(code, env)
        self.assertEqual(b'original', (self.root / 'photo.png').read_bytes())
        self.assertIn('photo_1.png copied to', notices[-1])
        self.assertEqual(b'nested image', (self.root / 'photo_1.png').read_bytes())
        env['rv'] = {'img_pick_nonce': '2', 'img_pick_file': '../bad.png'}
        exec(code, env)
        self.assertIn('Image pick failed or unsafe', notices[-1])
        self.assertIn('_SOUND_LIB NAME=r2_error', notices[-1])
        self.assertEqual([], self.staging())


if __name__ == '__main__':
    unittest.main(verbosity=2)
