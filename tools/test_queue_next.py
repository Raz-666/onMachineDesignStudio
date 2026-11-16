#!/usr/bin/env python3
"""Offline queue bookkeeping tests; no generator, watcher or printer runs."""
import ast
from pathlib import Path
import threading
import unittest
from unittest import mock

import os
if os.environ.get('R2_TEST_ENGINE') == 'active':
    import r2_postproc as pp
else:
    import r2_postproc_next as pp


class StopWorker(Exception):
    pass


def item(name, key):
    return (name, key, lambda: None, [], 0, 0, 0, 60)


def worker_ast():
    tree = ast.parse(Path(pp.__file__).read_text(encoding='utf8'))
    watch = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'watch')
    return next(n for n in watch.body if isinstance(n, ast.FunctionDef) and n.name == '_job_worker')


def run_cancel(mode, worker=None):
    state = {'queue': [item('first', 'a'), item('second', 'b')], 'keys': {'a', 'b'},
             'busy': False, 'lock': threading.Lock(), 'thread': None, 'zombie': None,
             'zombie_notice': 0, 'kill': mode}
    messages = []
    def push():
        if not state['queue'] or 'a' not in state['keys']:
            raise StopWorker()
    env = {'_JOB_STATE': state, '_genq_push': push,
           '_job_drop_pending_locked': pp._job_drop_pending_locked,
           '_moonraker_gcode': messages.append}
    worker = worker or worker_ast()
    exec(compile(ast.fix_missing_locations(ast.Module(body=[worker], type_ignores=[])),
                 '<isolated queue worker>', 'exec'), env)
    try:
        env['_job_worker']()
    except StopWorker:
        pass
    return state, messages


class QueueTests(unittest.TestCase):
    def test_cancel_skip_and_stop_drop_correct_keys_and_no_job_runs(self):
        for mode in ('SKIP', 'STOP'):
            with self.subTest(mode=mode):
                state, messages = run_cancel(mode)
                self.assertEqual({'b'} if mode == 'SKIP' else set(), state['keys'])
                self.assertEqual(['b'] if mode == 'SKIP' else [], [j[1] for j in state['queue']])
                self.assertIsNone(state['kill'])
                self.assertEqual(1, len(messages))
                self.assertIn('first dropped', messages[0])

    def test_drop_pending_preserves_running_key_and_container_identity(self):
        state = {'queue': [item('one', 'a'), item('two', 'b')], 'keys': {'a', 'b', 'running'}}
        reference = state['queue']
        self.assertEqual(2, pp._job_drop_pending_locked(state))
        self.assertIs(reference, state['queue'])
        self.assertEqual([], reference)
        self.assertEqual({'running'}, state['keys'])
        self.assertEqual(0, pp._job_drop_pending_locked(state))

    def test_old_dequeue_order_mutation_is_caught(self):
        worker = worker_ast()
        loop = next(n for n in worker.body if isinstance(n, ast.While))
        unpack = next(n for n in loop.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Tuple) and any(isinstance(e, ast.Name) and e.id == 'key' for e in t.elts) for t in n.targets))
        loop.body.remove(unpack)
        target = next(i for i, n in enumerate(loop.body) if isinstance(n, ast.Assign)
                      and isinstance(n.targets[0], ast.Subscript))
        loop.body.insert(target + 1, unpack)
        with self.assertRaises(UnboundLocalError):
            run_cancel('SKIP', worker)

    def test_zombie_key_remains_until_worker_thread_is_gone(self):
        for alive in (True, False):
            with self.subTest(alive=alive):
                thread = mock.Mock()
                thread.is_alive.return_value = alive
                state = {'queue': [], 'keys': {'running'}, 'busy': True, 'lock': threading.Lock(),
                         'thread': thread, 'zombie': ('stuck', 'running'), 'zombie_notice': 0}
                def stop(_): raise StopWorker()
                fake_time = mock.Mock()
                fake_time.monotonic.return_value = 1
                fake_time.sleep.side_effect = stop
                env = {'_JOB_STATE': state, '_JOB_YIELD': {}, 'time': fake_time,
                       '_job_led_done': lambda: None, '_moonraker_gcode': lambda *args: None}
                exec(compile(ast.fix_missing_locations(ast.Module(body=[worker_ast()], type_ignores=[])),
                             '<isolated queue worker>', 'exec'), env)
                with self.assertRaises(StopWorker): env['_job_worker']()
                self.assertEqual({'running'} if alive else set(), state['keys'])
                self.assertEqual(alive, state['busy'])
                self.assertEqual(('stuck', 'running') if alive else None, state['zombie'])

    def test_all_clear_paths_use_shared_pending_helper(self):
        tree = ast.parse(Path(pp.__file__).read_text(encoding='utf8'))
        watch = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'watch')
        calls = [n for n in ast.walk(watch) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == '_job_drop_pending_locked']
        self.assertEqual(5, len(calls))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                             and isinstance(n.func.value, ast.Subscript)
                             and isinstance(n.func.value.value, ast.Name)
                             and n.func.value.value.id == '_JOB_STATE'
                             and n.func.attr == 'clear' for n in ast.walk(watch)))


if __name__ == '__main__': unittest.main(verbosity=2)
