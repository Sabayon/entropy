# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')

import os
import tempfile
import unittest

from entropy.locks import SimpleFileLock, EntropyResourcesLock


class EntropyLocksTest(unittest.TestCase):

    def test_simple_lock(self):
        sfl = SimpleFileLock

        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(prefix="test_simple_lock")

            lock_map = {}
            self.assertEquals(True, sfl.acquire_lock(tmp_path, lock_map))
            self.assertIn(tmp_path, lock_map)
            self.assertTrue(lock_map[tmp_path] is not None)

            lock_map_new = {}
            self.assertEquals(False, sfl.acquire_lock(tmp_path, lock_map_new))
            self.assertNotIn(tmp_path, lock_map_new)
            self.assertIn(tmp_path, lock_map)

            sfl.release_lock(tmp_path, lock_map)

            self.assertEquals(True, sfl.acquire_lock(tmp_path, lock_map_new))
            self.assertIn(tmp_path, lock_map_new)
            self.assertTrue(lock_map_new[tmp_path] is not None)

            sfl.release_lock(tmp_path, lock_map_new)

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
            tmp_fd, tmp_path = tempfile.mkstemp(
                prefix="test_entropy_resources_lock")

            erl.path = lambda: tmp_path

            self.assertEquals(tmp_path, erl.path())

            self.assertEquals(True, erl.try_acquire_exclusive())
            self.assertEquals(1, counter_l[0])

            erl.release()

            self.assertEquals(True, erl.try_acquire_exclusive())
            self.assertEquals(2, counter_l[0])

            erl.release()

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(3, counter_l[0])

            erl.release()

            erl.acquire_exclusive()
            erl.release()

            erl.acquire_shared()
            erl.release()

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(6, counter_l[0])

            self.assertRaises(RuntimeError, erl.try_acquire_exclusive)

            self.assertEquals(True, erl.try_acquire_shared())
            self.assertEquals(7, counter_l[0])

            erl.release()

            self.assertRaises(RuntimeError, erl.try_acquire_exclusive)

            erl.release()

            self.assertEquals(True, erl.try_acquire_exclusive())

            erl.release()

            self.assertEquals(True, erl.wait_exclusive())

            erl.release()

            self.assertEquals(True, erl.wait_shared())

            erl.release()


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
            tmp_fd, tmp_path = tempfile.mkstemp(
                prefix="test_entropy_resources_lock")

            erl.path = lambda: tmp_path

            get_count = lambda: erl._file_lock_setup(erl.path())['count']

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


if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
