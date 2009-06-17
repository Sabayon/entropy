# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,'.')
sys.path.insert(0,'../')
import unittest
import os
from entropy.client.interfaces import Client
from entropy.const import etpConst, etpUi
from entropy.core import SystemSettings
from entropy.db import LocalRepository
from entropy.exceptions import RepositoryError
import _misc

class LocalRepositoryTest(unittest.TestCase):

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

    def test_package_install(self):

        pkg_metadata = {
            'accept_license': set([u'ZLIB']),
            'signatures': {'sha256': None, 'sha1': None, 'sha512': None},
            'removeidpackage': -1,
            'imagedir': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2/image',
            'download': u'packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2',
            'xpakpath': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2/xpak',
            'slot': u'0',
            'pkgdbpath': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2/edb/pkg.db',
            'versiontag': u'',
            'version': u'1.2.3-r1',
            'idpackage': 1,
            'xpakstatus': None,
            'unpackdir': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2',
            'revision': 1,
            'category': u'sys-libs',
            'repository': 'sys-libs:zlib-1.2.3-r1~1.tbz2',
            'xpakdir': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2/xpak/data',
            'merge_from': None,
            'atom': u'sys-libs/zlib-1.2.3-r1',
            'conflicts': set([]),
            'pkgpath': '/home/fabio/repos/entropy/libraries/tests/sys-libs:zlib-1.2.3-r1~1.tbz2',
            'removeconfig': False,
            'name': u'zlib',
            'install_source': 0,
            'triggers': {'install':
                {
                    'accept_license': set([u'ZLIB']),
                    'branch': u'4',
                    'eclasses': set([u'multilib', u'toolchain-funcs', u'eutils', u'portability', u'flag-o-matic']),
                    'xpakdir': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2/xpak/data',
                    'etpapi': 3,
                    'cxxflags': u'-Os -march=x86-64 -pipe',
                    'chost': u'x86_64-pc-linux-gnu',
                    'atom': u'sys-libs/zlib-1.2.3-r1',
                    'category': u'sys-libs',
                    'name': u'zlib',
                    'versiontag': u'',
                    'imagedir': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2/image',
                    'content': set([u'/lib64/libz.so', u'/usr/share/doc/zlib-1.2.3-r1', u'/usr/share/man', u'/usr/share', u'/usr/share/doc/zlib-1.2.3-r1/ChangeLog.bz2', u'/usr', u'/usr/share/doc/zlib-1.2.3-r1/FAQ.bz2', u'/usr/lib64', u'/usr/share/man/man3/zlib.3.bz2', u'/usr/include', u'/usr/lib64/libz.a', u'/lib64', u'/usr/share/doc/zlib-1.2.3-r1/algorithm.txt.bz2', u'/usr/share/doc/zlib-1.2.3-r1/README.bz2', u'/usr/include/zconf.h', u'/usr/lib64/libz.so', u'/usr/share/doc', u'/usr/include/zlib.h', u'/lib64/libz.so.1.2.3', u'/usr/share/man/man3', u'/lib64/libz.so.1']),
                    'version': u'1.2.3-r1',
                    'cflags': u'-Os -march=x86-64 -pipe',
                    'spm_phases': None,
                    'unpackdir': u'/var/tmp/entropy/packages/amd64/4/sys-libs:zlib-1.2.3-r1~1.tbz2',
                    'revision': 1}
                },
            'configprotect_data': [],
            'checksum': u'5b2c4dadef86b3e61129a23ad10367ab',
            'messages': [],
            'remove_metaopts': {'removeconfig': True},
            'steps': ['unpack', 'preinstall', 'install', 'postinstall', 'logmessages', 'cleanup'],
            'smartpackage': False
        }

        test_pkg = _misc.get_test_entropy_package()
        rc, atoms_contained = self.Client.add_tbz2_to_repos(test_pkg)
        self.assertEqual(0, rc)
        self.assertNotEqual([],atoms_contained)
        for match in atoms_contained: # it's just one
            pkg = self.Client.Package()
            pkg.prepare(match, "install")
            del pkg.infoDict['triggers']['install']['trigger']
            self.assertEqual(pkg.infoDict, pkg_metadata)

    def test_package_source(self):
        pass

if __name__ == '__main__':
    unittest.main()
