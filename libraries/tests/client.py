# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'client')
sys.path.insert(0, '../../client')
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import os
import shutil
import tempfile
from entropy.client.interfaces import Client
from entropy.const import etpConst, etpUi
from entropy.core.settings.base import SystemSettings
from entropy.db import EntropyRepository
from entropy.exceptions import RepositoryError
import tests._misc as _misc

class EntropyRepositoryTest(unittest.TestCase):

    def setUp(self):
        self.mem_repoid = "mem_repo"
        self.mem_repo_desc = "This is a testing repository"
        self.Client = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)
        # fake clientDbconn
        self.Client.clientDbconn = self.Client.open_memory_database(
            dbname = etpConst['clientdbid'])
        self.Spm = self.Client.Spm()
        self.SystemSettings = SystemSettings()
        self.test_pkgs = [_misc.get_entrofoo_test_package()]

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()
        self.Client.destroy()

    def test_singleton(self):
        myclient = Client(noclientdb = 2)
        self.assert_(myclient is self.Client)
        myclient.destroy()
        self.assert_(myclient.is_destroyed())
        self.assert_(self.Client.is_destroyed())
        myclient2 = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)
        self.assert_(myclient is not myclient2)
        myclient2.destroy()
        self.assert_(myclient2.is_destroyed())

    def test_constant_backup(self):
        const_key = 'foo_foo_foo'
        const_val = set([1, 2, 3])
        etpConst[const_key] = const_val
        self.Client.backup_constant(const_key)
        self.Client.reload_constants()
        self.assertEqual(True, const_key in etpConst)
        self.assertEqual(const_val, etpConst.get(const_key))
        # now remove
        etpConst['backed_up'].pop(const_key)
        self.Client.reload_constants()
        self.assertEqual(False, const_key in etpConst)
        self.assertEqual(None, etpConst.get(const_key))

    def test_syssetting_backup(self):
        key1 = 'foo_foo_foo2'
        key2 = 'asdasdadsadas'
        val1 = set([1, 2, 3])
        val2 = None
        foo_data = {
            key1: val1,
            key2: val2,
        }
        self.SystemSettings.update(foo_data)
        self.SystemSettings.set_persistent_setting(foo_data)
        self.SystemSettings.clear()
        self.assertEqual(True, key1 in self.SystemSettings)
        self.assertEqual(True, key2 in self.SystemSettings)
        self.assertEqual(val1, self.SystemSettings.get(key1))
        self.assertEqual(val2, self.SystemSettings.get(key2))

        # now remove
        self.SystemSettings.unset_persistent_setting(key1)
        self.SystemSettings.clear()
        self.assertEqual(False, key1 in self.SystemSettings)
        self.assertEqual(True, key2 in self.SystemSettings)

        self.SystemSettings.unset_persistent_setting(key2)
        self.SystemSettings.clear()
        self.assertEqual(False, key1 in self.SystemSettings)
        self.assertEqual(False, key2 in self.SystemSettings)

    def test_memory_repository(self):
        dbconn = self.Client.init_generic_memory_repository(
            self.mem_repoid, self.mem_repo_desc)
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = dbconn.handlePackage(data)
        self.assertEqual(data, new_data)
        self.Client.remove_repository(self.mem_repoid)
        self.assertNotEqual(
            self.Client._memory_db_instances.get(self.mem_repoid), dbconn)
        def test_load():
            etpUi['mute'] = True
            self.Client.open_repository(self.mem_repoid)
            etpUi['mute'] = False
        self.assertRaises(RepositoryError, test_load)

    def test_package_repository(self):
        test_pkg = _misc.get_test_entropy_package()
        rc, atoms_contained = self.Client.add_package_to_repos(test_pkg)
        self.assertEqual(0, rc)
        self.assertNotEqual([], atoms_contained)
        for idpackage, repoid in atoms_contained:
            dbconn = self.Client.open_repository(repoid)
            self.assertNotEqual(None, dbconn.getPackageData(idpackage))
            self.assertNotEqual(None, dbconn.retrieveAtom(idpackage))

    def test_package_installation(self):
        for pkg_path, pkg_atom in self.test_pkgs:
            self._do_pkg_test(pkg_path, pkg_atom)

    def _do_pkg_test(self, pkg_path, pkg_atom):

        # this test might be considered controversial, for now, let's keep it
        # here, we use equo stuff to make sure it keeps working
        import text_smart

        # we need to tweak the default unpack dir to make pkg install available
        # for uids != 0
        temp_unpack = tempfile.mkdtemp()
        old_unpackdir = etpConst['entropyunpackdir']
        etpConst['entropyunpackdir'] = temp_unpack

        fake_root = tempfile.mkdtemp()
        pkg_dir = tempfile.mkdtemp()
        inst_dir = tempfile.mkdtemp()

        rc = text_smart.InflateHandler([pkg_path], pkg_dir)
        self.assert_(rc == 0)
        self.assert_(os.listdir(pkg_dir))

        etp_pkg = os.path.join(pkg_dir, os.listdir(pkg_dir)[0])
        self.assert_(os.path.isfile(etp_pkg))

        status, matches = self.Client.add_package_to_repos(etp_pkg)
        self.assert_(status == 0)
        self.assert_(matches)
        for match in matches:
            my_p = self.Client.Package()
            my_p.prepare(match, "install", {})
            # unit testing metadata setting, of course, undocumented
            my_p.pkgmeta['unittest_root'] = fake_root
            rc = my_p.run()
            self.assert_(rc == 0)

        # remove pkg
        idpackages = self.Client.clientDbconn.listAllIdpackages()
        for idpackage in idpackages:
            my_p = self.Client.Package()
            my_p.prepare((idpackage,), "remove", {})
            rc = my_p.run()
            self.assert_(rc == 0)

        # done installing
        shutil.rmtree(pkg_dir, True)
        shutil.rmtree(temp_unpack, True)
        shutil.rmtree(fake_root, True)

        # restore orig const value
        etpConst['entropyunpackdir'] = old_unpackdir


if __name__ == '__main__':
    unittest.main()
