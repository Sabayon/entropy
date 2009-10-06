# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import tests._misc as _misc
from entropy.transceivers import UrlFetcher, MultipleUrlFetcher
from entropy.const import etpUi

class TransceiversTest(unittest.TestCase):

    def setUp(self):
        self._random_file = _misc.get_random_file()
        self._random_file_md5 = _misc.get_random_file_md5()

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def test_urlfetcher_file_fetch(self):

        file_path = "file://" + os.path.realpath(self._random_file)
        ck_f = open(self._random_file_md5)
        ck_sum = ck_f.readline().strip().split()[0]
        ck_f.close()
        path_to_save = os.path.join(os.path.dirname(self._random_file),
            "test_urlfetcher")

        fetcher = UrlFetcher(file_path, path_to_save,
            show_speed = False, resume = False)
        rc = fetcher.download()
        self.assertEqual(rc, ck_sum)
        os.remove(path_to_save)

    def test_multiple_urlfetcher_file_fetch(self):

        file_path = "file://" + os.path.realpath(self._random_file)
        ck_f = open(self._random_file_md5, "r")
        ck_sum = ck_f.readline().strip().split()[0]
        ck_f.close()
        path_to_save = os.path.join(os.path.dirname(self._random_file),
            "test_urlfetcher")

        etpUi['mute'] = True
        fetcher = MultipleUrlFetcher([(file_path, path_to_save,)],
            show_speed = False, resume = False)
        rc = fetcher.download()
        etpUi['mute'] = False
        self.assertEqual(rc.pop(1), ck_sum)
        os.remove(path_to_save)

if __name__ == '__main__':
    unittest.main()
