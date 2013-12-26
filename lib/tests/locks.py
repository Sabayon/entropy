# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')

import threading
import time
import os
import unittest

from entropy.const import const_mkstemp
from entropy.locks import SimpleFileLock, EntropyResourcesLock


class EntropyLocksTest(unittest.TestCase):

    def test_simple_lock(self):
        sfl = SimpleFileLock

        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = const_mkstemp(prefix="test_simple_lock")

            lock_map = {}
            self.assertEquals(True, sfl.acquire(tmp_path, lock_map))
            self.assertIn(tmp_path, lock_map)
            self.assertTrue(lock_map[tmp_path] is not None)

            lock_map_new = {}
            self.assertEquals(False, sfl.acquire(tmp_path, lock_map_new))
            self.assertNotIn(tmp_path, lock_map_new)
            self.assertIn(tmp_path, lock_map)

            sfl.release(tmp_path, lock_map)

            self.assertEquals(True, sfl.acquire(tmp_path, lock_map_new))
            self.assertIn(tmp_path, lock_map_new)
            self.assertTrue(lock_map_new[tmp_path] is not None)

            sfl.release(tmp_path, lock_map_new)

        finally:
            if tmp_fd is not None:
                os.close(tmp_fd)
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def test_entropy_resources_lock(self):

        erl = EntropyResourcesLock()

        counter_l = [0]

        def _hook():
            counter_l[0] += 1

        erl.add_post_acquire_hook(_hook)

        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = const_mkstemp(
                prefix="test_entropy_resources_lock")

            erl.path = lambda: tmp_path

            self.assertEquals(tmp_path, erl.path())

            self.assertFalse(erl.is_already_acquired())

            self.assertEquals(True, erl.try_acquire_exclusive())
            self.assertEquals(1, counter_l[0])

            self.assertTrue(erl.is_already_acquired())

            erl.release()

            self.assertFalse(erl.is_already_acquired())

            self.assertEquals(True, erl.try_acquire_exclusive())
            self.assertEquals(2, counter_l[0])

            erl.release()

            self.assertFalse(erl.is_already_acquired())

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(3, counter_l[0])

            self.assertTrue(erl.is_already_acquired())

            erl.release()

            self.assertFalse(erl.is_already_acquired())

            erl.acquire_exclusive()
            erl.release()

            self.assertFalse(erl.is_already_acquired())

            erl.acquire_shared()
            erl.release()

            self.assertFalse(erl.is_already_acquired())

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(6, counter_l[0])

            self.assertTrue(erl.is_already_acquired())

            self.assertRaises(RuntimeError, erl.try_acquire_exclusive)

            self.assertTrue(erl.is_already_acquired())

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(7, counter_l[0])

            erl.release()

            self.assertTrue(erl.is_already_acquired())

            self.assertRaises(RuntimeError, erl.try_acquire_exclusive)

            self.assertTrue(erl.is_already_acquired())

            erl.release()

            self.assertEquals(True, erl.try_acquire_exclusive())

            erl.release()

            self.assertFalse(erl.is_already_acquired())

            self.assertEquals(True, erl.wait_exclusive())

            self.assertTrue(erl.is_already_acquired())

            erl.release()

            self.assertFalse(erl.is_already_acquired())

            self.assertEquals(True, erl.wait_shared())

            self.assertTrue(erl.is_already_acquired())

            erl.release()

            self.assertFalse(erl.is_already_acquired())

        finally:
            if tmp_fd is not None:
                os.close(tmp_fd)
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def test_entropy_resources_lock_exception(self):

        erl = EntropyResourcesLock()

        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = const_mkstemp(
                prefix="test_entropy_resources_lock")

            erl.path = lambda: tmp_path

            get_count = lambda: erl._file_lock_setup()['count']

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertRaises(RuntimeError, erl.try_acquire_exclusive)

            erl.release()

            self.assertEquals(True, erl.try_acquire_exclusive())

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(True, erl.try_acquire_shared())

            self.assertEquals(4, get_count())
            erl.release()

            self.assertEquals(3, get_count())
            erl.release()

            self.assertEquals(2, get_count())
            erl.release()

            self.assertEquals(1, get_count())
            erl.release()

            self.assertEquals(0, get_count())

            self.assertRaises(RuntimeError, erl.release)


        finally:
            if tmp_fd is not None:
                os.close(tmp_fd)
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def test_entropy_resources_lock_threads(self):
        """
        ResourceLock multithreaded test.

        This test ensures that the resource is also contended
        between threads, not just processes.
        """
        erl = EntropyResourcesLock()
        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = const_mkstemp(
                prefix="test_entropy_resources_lock")

            erl.path = lambda: tmp_path

            get_count = lambda: erl._file_lock_setup()['count']
            get_ref = lambda: erl._file_lock_setup()['ref']
            other_thread_count = [0]
            other_thread_loop_count = [0]
            cond = threading.Condition()

            self.assertEquals(True, erl.try_acquire_exclusive())
            self.assertEquals(1, get_count())
            self.assertNotEquals(None, get_ref())
            self.assertEquals(0, other_thread_count[0])

            def try_acquire_thread():
                milliseconds = 10 * 1000
                acquired = False
                loop_n = 0
                while milliseconds:
                    self.assertEquals(None, get_ref())

                    acquired = erl.try_acquire_exclusive()
                    if loop_n == 0:
                        self.assertFalse(acquired)

                    if acquired:
                        self.assertNotEquals(None, get_ref())
                        other_thread_count[0] += 1
                        break

                    time.sleep(0.100)
                    milliseconds -= 100
                    loop_n += 1
                    with cond:
                        other_thread_loop_count[0] += 1
                        cond.notify()

                self.assertTrue(acquired)

            th = threading.Thread(target=try_acquire_thread,
                                  name="TryAcquireThread")
            th.start()

            with cond:
                while other_thread_loop_count[0] < 1:
                    cond.wait()

            erl.release()
            th.join()
            self.assertEquals(1, other_thread_count[0])

        finally:
            if tmp_fd is not None:
                os.close(tmp_fd)
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
