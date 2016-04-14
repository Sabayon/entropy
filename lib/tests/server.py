# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import os
import shutil
from entropy.server.interfaces import Server
from entropy.const import etpConst, initconfig_entropy_constants, etpSys
from entropy.core.settings.base import SystemSettings
from entropy.db import EntropyRepository
from entropy.db.cache import EntropyRepositoryCacher, \
    EntropyRepositoryCachePolicies
from entropy.exceptions import RepositoryError
import entropy.tools
import tests._misc as _misc

class EntropyRepositoryTest(unittest.TestCase):

    def setUp(self):
        self.default_repo = "foo"
        etpConst['defaultserverrepositoryid'] = self.default_repo
        etpConst['uid'] = 0

        # create fake server repo
        self.Server = Server(fake_default_repo_id = self.default_repo,
            fake_default_repo_desc = 'foo desc', fake_default_repo = True)
        foo_db = self.Server.open_server_repository(self.default_repo,
            read_only = False, lock_remote = False, is_new = True)
        foo_db.initializeRepository()

        # force cache policy to avoid system dependent behaviour (memory size
        # detection)
        EntropyRepositoryCachePolicies.DEFAULT_CACHE_POLICY = \
                EntropyRepositoryCachePolicies.ALL


    def tearDown(self):
        """
        tearDown is run after each test
        """
        self.Server.remove_repository(self.default_repo)
        # calling destroy() and shutdown()
        # need to call destroy() directly to remove all the SystemSettings
        # plugins because shutdown() doesn't, since it's meant to be called
        # right before terminating the process
        self.Server.destroy()
        self.Server.shutdown()

    def test_server_instance(self):
        self.assertEqual(self.default_repo, self.Server.repository())

    def test_server_repo(self):
        dbconn = self.Server.open_server_repository(
            self.Server.repository())
        self.assertEqual(dbconn.temporary(), True)

    def test_server_repo_internal_cache(self):
        spm = self.Server.Spm()
        dbconn = self.Server.open_server_repository(
            self.Server.repository())
        test_pkg = _misc.get_test_package()
        data = spm.extract_package_metadata(test_pkg)
        idpackage = dbconn.handlePackage(data)
        # now it should be empty
        cacher = EntropyRepositoryCacher()
        self.assertEqual(cacher.keys(), [])
        self.assertNotEqual(dbconn.retrieveRevision(idpackage), None)
        # now it should be filled
        cache_key = dbconn._getLiveCacheKey() + 'retrieveRevision'
        self.assertEqual(
            cacher.get(cache_key),
            {1: 0})
        # clear again
        dbconn.clearCache()
        self.assertEqual(cacher.keys(), [])

    def test_rev_bump(self):
        spm = self.Server.Spm()
        test_db = self.Server.open_server_repository(
            self.Server.repository())
        test_pkg = _misc.get_test_package()
        data = spm.extract_package_metadata(test_pkg)
        idpackage = test_db.handlePackage(data)
        rev = test_db.retrieveRevision(idpackage)
        idpackage2 = test_db.handlePackage(data)
        rev2 = test_db.retrieveRevision(idpackage2)
        data2 = test_db.getPackageData(idpackage2)
        self.assertNotEqual(data['revision'], data2['revision'])
        data.pop('revision')
        data2.pop('revision')

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(data2)
        self.assertEqual(data, data2)

        self.assertEqual(idpackage, 1)
        self.assertEqual(idpackage2, 2)
        self.assertEqual(rev, 0)
        self.assertEqual(rev2, 1)

    def test_rev_bump_2(self):
        spm = self.Server.Spm()
        test_db = self.Server.open_server_repository(
            self.Server.repository())
        test_pkg = _misc.get_test_package()
        data = spm.extract_package_metadata(test_pkg)
        idpackage = test_db.handlePackage(data)
        rev = test_db.retrieveRevision(idpackage)
        test_db.removePackage(idpackage)
        idpackage2 = test_db.handlePackage(data)
        rev2 = test_db.retrieveRevision(idpackage2)
        data2 = test_db.getPackageData(idpackage2)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(data2)
        self.assertEqual(data, data2)

        self.assertEqual(idpackage, 1)
        self.assertEqual(idpackage2, 2)
        self.assertEqual(rev, 0)
        self.assertEqual(rev2, 0)

    def test_package_injection(self):
        test_pkg = _misc.get_test_entropy_package()
        tmp_test_pkg = test_pkg+".tmp"
        shutil.copy2(test_pkg, tmp_test_pkg)
        added = self.Server.add_packages_to_repository(
            self.Server.repository(), [([tmp_test_pkg], False,)],
            ask = False)
        self.assertEqual(set([1]), added)
        def do_stat():
            os.stat(tmp_test_pkg)
        self.assertRaises(OSError, do_stat)
        dbconn = self.Server.open_server_repository(
            self.Server.repository())
        self.assertNotEqual(None, dbconn.retrieveAtom(1))

    def test_package_injection2(self):
        test_pkg = _misc.get_test_entropy_package5()
        tmp_test_pkg = test_pkg+".tmp"
        shutil.copy2(test_pkg, tmp_test_pkg)
        added = self.Server.add_packages_to_repository(
            self.Server.repository(), [([tmp_test_pkg], False,)],
            ask = False)
        self.assertEqual(set([1]), added)
        def do_stat():
            os.stat(tmp_test_pkg)
        self.assertRaises(OSError, do_stat)
        dbconn = self.Server.open_server_repository(
            self.Server.repository())
        self.assertNotEqual(None, dbconn.retrieveAtom(1))

    def test_constant_backup(self):
        const_key = 'foo_foo_foo'
        const_val = set([1, 2, 3])
        etpConst[const_key] = const_val
        self.Server._backup_constant(const_key)
        # reload constants
        initconfig_entropy_constants(etpSys['rootdir'])
        self.Server._settings.clear()
        self.assertEqual(True, const_key in etpConst)
        self.assertEqual(const_val, etpConst.get(const_key))
        # now remove
        etpConst['backed_up'].pop(const_key)
        # reload constants
        initconfig_entropy_constants(etpSys['rootdir'])
        self.Server._settings.clear()
        self.assertEqual(False, const_key in etpConst)
        self.assertEqual(None, etpConst.get(const_key))

if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
