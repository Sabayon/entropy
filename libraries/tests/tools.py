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
import subprocess
import shutil
import stat

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

    def test_extract_xpak_only(self):

        pkg_path = _misc.get_test_xpak_empty_package()
        tmp_path = tempfile.mkdtemp()
        out_path = et.extract_xpak(pkg_path, tmp_path)

        self.assertNotEqual(out_path, None)
        self.assert_(os.listdir(out_path))

        shutil.rmtree(tmp_path, True)

    def test_remove_edb(self):

        tmp_path = tempfile.mkdtemp()

        for test_pkg in self.test_pkgs:
            self.assert_(et.is_entropy_package_file(test_pkg))
            out_path = et.remove_edb(test_pkg, tmp_path)
            self.assertNotEqual(out_path, None)
            self.assert_(os.path.isfile(out_path))
            self.assert_(not et.is_entropy_package_file(out_path))

    def test_uncompress_tar_bz2(self):

        pkg_path = _misc.get_test_entropy_package4()
        tmp_dir = tempfile.mkdtemp()
        fd, tmp_file = tempfile.mkstemp()

        path_perms = {}

        # try with tar first
        args = ["tar", "xjfp", pkg_path, "-C", tmp_dir]
        proc = subprocess.Popen(args, stdout = fd, stderr = fd)
        rc = proc.wait()
        self.assert_(not rc)
        os.close(fd)

        for currentdir, subdirs, files in os.walk(tmp_dir):
            for file in files:
                path = os.path.join(currentdir, file)
                fstat = os.lstat(path)
                mode = stat.S_IMODE(fstat.st_mode)
                uid, gid = fstat.st_uid, fstat.st_gid
                path_perms[path] = (mode, uid, gid,)

        self.assert_(path_perms)
        shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)

        # now try with our function
        rc = et.uncompress_tar_bz2(pkg_path, tmp_dir)
        self.assert_(not rc)

        for currentdir, subdirs, files in os.walk(tmp_dir):
            for file in files:
                path = os.path.join(currentdir, file)
                fstat = os.lstat(path)
                mode = stat.S_IMODE(fstat.st_mode)
                uid, gid = fstat.st_uid, fstat.st_gid
                mystat = (mode, uid, gid,)
                try:
                    self.assertEqual(mystat, path_perms.get(path))
                except AssertionError:
                    print "ouch", path, "my:", mystat
                    raise


        shutil.rmtree(tmp_dir)



if __name__ == '__main__':
    unittest.main()
