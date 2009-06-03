# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0,'.')
sys.path.insert(0,'../')
import unittest
import entropy.tools as et
from entropy.client.interfaces import Client
import _misc
import tempfile
import shutil

class MiscTest(unittest.TestCase):

    def setUp(self):
        self.Client = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)
        self.test_pkg = _misc.get_test_entropy_package()
        self.test_pkg2 = _misc.get_test_entropy_package2()
        self.test_pkg3 = _misc.get_test_entropy_package3()
        self.test_pkgs = [self.test_pkg, self.test_pkg2, self.test_pkg3]

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()
        self.Client.destroy()

    def test_extract_edb(self):

        fd, tmp_path = tempfile.mkstemp()

        for test_pkg in self.test_pkgs:
            out_path = et.extract_edb(test_pkg, tmp_path)
            self.assertNotEqual(out_path, None)
            dbconn = self.Client.open_generic_database(out_path)
            dbconn.validateDatabase()
            dbconn.listAllIdpackages()
            dbconn.closeDB()

        os.close(fd)
        os.remove(tmp_path)

    def test_extract_xpak(self):

        tmp_path = tempfile.mkdtemp()

        for test_pkg in self.test_pkgs:
            out_path = et.extract_xpak(test_pkg, tmp_path)
            self.assertNotEqual(out_path, None)
            self.assert_(os.listdir(out_path))

        shutil.rmtree(tmp_path, True)

if __name__ == '__main__':
    unittest.main()
