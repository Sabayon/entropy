# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,'.')
sys.path.insert(0,'../')
import unittest
import os
from entropy.client.interfaces import Client
from entropy.const import etpConst, etpUi
from entropy.core import SystemSettings
from entropy.db import EntropyRepository
from entropy.exceptions import RepositoryError
import _misc

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

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()
        self.Client.destroy()

    def test_constant_backup(self):
        const_key = 'foo_foo_foo'
        const_val = set([1,2,3])
        etpConst[const_key] = const_val
        self.Client.backup_constant(const_key)
        self.Client.reload_constants()
        self.assertEqual(True, etpConst.has_key(const_key))
        self.assertEqual(const_val, etpConst.get(const_key))
        # now remove
        etpConst['backed_up'].pop(const_key)
        self.Client.reload_constants()
        self.assertEqual(False, etpConst.has_key(const_key))
        self.assertEqual(None, etpConst.get(const_key))

    def test_syssetting_backup(self):
        key1 = 'foo_foo_foo2'
        key2 = 'asdasdadsadas'
        val1 = set([1,2,3])
        val2 = None
        foo_data = {
            key1: val1,
            key2: val2,
        }
        self.SystemSettings.update(foo_data)
        self.SystemSettings.set_persistent_setting(foo_data)
        self.SystemSettings.clear()
        self.assertEqual(True,self.SystemSettings.has_key(key1))
        self.assertEqual(True,self.SystemSettings.has_key(key2))
        self.assertEqual(val1,self.SystemSettings.get(key1))
        self.assertEqual(val2,self.SystemSettings.get(key2))

        # now remove
        self.SystemSettings.unset_persistent_setting(key1)
        self.SystemSettings.clear()
        self.assertEqual(False,self.SystemSettings.has_key(key1))
        self.assertEqual(True,self.SystemSettings.has_key(key2))

        self.SystemSettings.unset_persistent_setting(key2)
        self.SystemSettings.clear()
        self.assertEqual(False,self.SystemSettings.has_key(key1))
        self.assertEqual(False,self.SystemSettings.has_key(key2))

    def test_memory_repository(self):
        dbconn = self.Client.init_generic_memory_repository(
            self.mem_repoid, self.mem_repo_desc)
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_pkg_metadata(test_pkg, silent = True)
        idpackage, rev, new_data = dbconn.handlePackage(data)
        self.assertEqual(data, new_data)
        self.Client.remove_repository(self.mem_repoid)
        self.assertNotEqual(
            self.Client._memory_db_instances.get(self.mem_repoid),dbconn)
        def test_load():
            etpUi['mute'] = True
            self.Client.open_repository(self.mem_repoid)
            etpUi['mute'] = False
        self.assertRaises(RepositoryError, test_load)

    def test_package_repository(self):
        test_pkg = _misc.get_test_entropy_package()
        rc, atoms_contained = self.Client.add_tbz2_to_repos(test_pkg)
        self.assertEqual(0, rc)
        self.assertNotEqual([],atoms_contained)
        for idpackage, repoid in atoms_contained:
            dbconn = self.Client.open_repository(repoid)
            self.assertNotEqual(None, dbconn.getPackageData(idpackage))
            self.assertNotEqual(None, dbconn.retrieveAtom(idpackage))


if __name__ == '__main__':
    unittest.main()
