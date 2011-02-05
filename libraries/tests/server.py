# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import os
import shutil
from entropy.server.interfaces import Server
from entropy.const import etpConst
from entropy.core.settings.base import SystemSettings
from entropy.db import EntropyRepository
from entropy.exceptions import RepositoryError
import entropy.tools
import tests._misc as _misc

class EntropyRepositoryTest(unittest.TestCase):

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()
        self.default_repo = "foo"
        etpConst['defaultserverrepositoryid'] = self.default_repo
        etpConst['uid'] = 0

        # create fake server repo
        self.Server = Server(fake_default_repo_id = self.default_repo,
            fake_default_repo_desc = 'foo desc', fake_default_repo = True)
        foo_db = self.Server.open_server_repository(self.default_repo,
            read_only = False, lock_remote = False, is_new = True)
        foo_db.initializeRepository()


    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()
        # calling destroy() and shutdown()
        # need to call destroy() directly to remove all the SystemSettings
        # plugins because shutdown() doesn't, since it's meant to be called
        # right before terminating the process
        self.Server.destroy()
        self.Server.shutdown()

    def test_server_instance(self):
        self.assertEqual(self.default_repo, self.Server.default_repository)

    def test_server_repo(self):
        dbconn = self.Server.open_server_repository(
            self.Server.default_repository)
        self.assertEqual(dbconn.temporary(), True)

    def test_server_repo_internal_cache(self):
        spm = self.Server.Spm()
        dbconn = self.Server.open_server_repository(
            self.Server.default_repository)
        test_pkg = _misc.get_test_package()
        data = spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = dbconn.handlePackage(data)
        # now it should be empty
        self.assertEqual(EntropyRepository._LIVE_CACHE, {})
        self.assertNotEqual(dbconn.retrieveRevision(idpackage), None)
        # now it should be filled
        cache_key = dbconn._EntropyRepository__getLiveCacheKey() + \
            'retrieveRevision'
        self.assertEqual(
            EntropyRepository._LIVE_CACHE[cache_key],
            {1: 0})
        # clear again
        dbconn.clearCache()
        self.assertEqual(EntropyRepository._LIVE_CACHE, {})

    def test_rev_bump(self):
        spm = self.Server.Spm()
        test_db = self.Server.open_server_repository(
            self.Server.default_repository)
        test_pkg = _misc.get_test_package()
        data = spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = test_db.handlePackage(data)
        idpackage2, rev2, new_data2 = test_db.handlePackage(data)
        self.assertEqual(new_data, new_data2)
        self.assertEqual(idpackage, 1)
        self.assertEqual(idpackage2, 2)
        self.assertEqual(rev, 0)
        self.assertEqual(rev2, 1)

    def test_rev_bump_2(self):
        spm = self.Server.Spm()
        test_db = self.Server.open_server_repository(
            self.Server.default_repository)
        test_pkg = _misc.get_test_package()
        data = spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = test_db.handlePackage(data)
        test_db.removePackage(idpackage)
        idpackage2, rev2, new_data2 = test_db.handlePackage(data)
        self.assertEqual(new_data, new_data2)
        self.assertEqual(idpackage, 1)
        self.assertEqual(idpackage2, 2)
        self.assertEqual(rev, 0)
        self.assertEqual(rev2, 0)

    def test_package_injection(self):
        test_pkg = _misc.get_test_entropy_package()
        tmp_test_pkg = test_pkg+".tmp"
        shutil.copy2(test_pkg, tmp_test_pkg)
        added = self.Server.add_packages_to_repository(
            self.Server.default_repository, [(tmp_test_pkg, False,)],
            ask = False)
        self.assertEqual(set([1]), added)
        def do_stat():
            os.stat(tmp_test_pkg)
        self.assertRaises(OSError, do_stat)
        dbconn = self.Server.open_server_repository(
            self.Server.default_repository)
        self.assertNotEqual(None, dbconn.retrieveAtom(1))

    def test_package_injection2(self):
        test_pkg = _misc.get_test_entropy_package5()
        tmp_test_pkg = test_pkg+".tmp"
        shutil.copy2(test_pkg, tmp_test_pkg)
        added = self.Server.add_packages_to_repository(
            self.Server.default_repository, [(tmp_test_pkg, False,)],
            ask = False)
        self.assertEqual(set([1]), added)
        def do_stat():
            os.stat(tmp_test_pkg)
        self.assertRaises(OSError, do_stat)
        dbconn = self.Server.open_server_repository(
            self.Server.default_repository)
        self.assertNotEqual(None, dbconn.retrieveAtom(1))

if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
    entropy.tools.kill_threads()
    raise SystemExit(0)
