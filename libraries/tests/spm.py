# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import entropy.tools as et
from entropy.client.interfaces import Client
import tests._misc as _misc
import tempfile
import shutil

class SpmTest(unittest.TestCase):

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

    def test_init(self):
        spm = self.Client.Spm()
        spm2 = self.Client.Spm()
        self.assert_(spm is spm2)
        spm_class = self.Client.Spm_class()
        spm_class2 = self.Client.Spm_class()
        self.assert_(spm_class is spm_class2)

    def test_basic_methods(self):
        spm = self.Client.Spm()
        spm_class = self.Client.Spm_class()

        path = spm.get_user_installed_packages_file()
        self.assert_(path)

        groups = spm_class.get_package_groups()
        self.assert_(isinstance(groups, dict))

        keys = spm.package_metadata_keys()
        self.assert_(isinstance(keys, list))

        cache_dir = spm.get_cache_directory()
        self.assert_(cache_dir)

        sys_pkgs = spm.get_system_packages()
        self.assert_(sys_pkgs)
        self.assert_(isinstance(sys_pkgs, list))

        path1 = spm.get_merge_protected_paths_mask()
        path2 = spm.get_merge_protected_paths()
        self.assert_(isinstance(path1, list))
        self.assert_(isinstance(path2, list))

        pkg = spm.convert_from_entropy_package_name("app-foo/foo")
        self.assert_(pkg)

    def test_portage_xpak(self):

        spm_class = self.Client.Spm_class()
        if spm_class.PLUGIN_NAME != "portage":
            return

        sums = {}
        paths = []

        import entropy.xpak as xpak
        temp_unpack = tempfile.mkdtemp()
        temp_unpack2 = tempfile.mkdtemp()
        test_pkg = os.path.join(temp_unpack2, "test.pkg")
        dbdir = _misc.get_entrofoo_test_spm_portage_dir()

        for path in os.listdir(dbdir):
            xpath = os.path.join(dbdir, path)
            paths.append(xpath)
            sums[path] = et.md5sum(xpath)

        et.compress_files(test_pkg, paths)
        comp_file = xpak.tbz2(test_pkg)
        result = comp_file.recompose(dbdir)

        shutil.rmtree(temp_unpack)
        os.mkdir(temp_unpack)

        # now extract xpak
        new_sums = {}
        et.extract_xpak(test_pkg, tmpdir = temp_unpack)
        for path in os.listdir(temp_unpack):
            xpath = os.path.join(temp_unpack, path)
            new_sums[path] = et.md5sum(xpath)

        self.assertEqual(sums, new_sums)

        shutil.rmtree(temp_unpack)
        shutil.rmtree(temp_unpack2)

if __name__ == '__main__':
    unittest.main()
