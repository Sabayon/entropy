# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import os
import time
import threading

from entropy.client.interfaces import Client
from entropy.const import etpConst, const_convert_to_unicode, \
    const_convert_to_rawstring, const_mkstemp
from entropy.output import set_mute
from entropy.core.settings.base import SystemSettings
from entropy.misc import ParallelTask
from entropy.db import EntropyRepository
import tests._misc as _misc

import entropy.dep
import entropy.tools


class EntropyRepositoryTest(unittest.TestCase):

    def setUp(self):
        self.Client = Client(installed_repo = -1, indexing = False,
            xcache = False, repo_validation = False)
        self.Spm = self.Client.Spm()
        self.test_db_name = "test_suite"
        self.test_db = self.__open_test_db(":memory:")
        # GenericRepository supports package masking if this property is set
        self.test_db.enable_mask_filter = True
        self.test_db2 = self.__open_test_db(":memory:")
        # GenericRepository supports package masking if this property is set
        self.test_db2.enable_mask_filter = True
        self._settings = SystemSettings()
        # since package files have been produced on amd64, add the same
        # arch to etpConst['keywords'] to avoid atomMatch failures on x86
        # and arm/other arches.
        self._original_keywords = etpConst['keywords'].copy()
        etpConst['keywords'].add("~amd64")
        etpConst['keywords'].add("amd64")

    def tearDown(self):
        """
        tearDown is run after each test
        """
        self.test_db.close()
        self.test_db2.close()
        # calling destroy() and shutdown()
        # need to call destroy() directly to remove all the SystemSettings
        # plugins because shutdown() doesn't, since it's meant to be called
        # right before terminating the process
        self.Client.destroy()
        self.Client.shutdown()
        etpConst['keywords'] = self._original_keywords.copy()

    def __open_test_db(self, tmp_path):
        return self.Client.open_temp_repository(name = self.test_db_name,
            temp_file = tmp_path)

    def test_db_clearcache(self):
        self.test_db.clearCache()

    def test_treeupdates_config_files_update(self):
        files = _misc.get_config_files_updates_test_files()
        actions = [
            "move app-admin/anaconda app-admin/fuckaconda",
            "slotmove app-admin/anaconda 0 2", # unsupported
            "move media-sound/xmms2 media-sound/deadashell",
            "move media-sound/pulseaudio media-sound/idiotaudio",
            "move sys-auth/pambase sys-auth/fuckbase",
            "move sys-devel/gcc sys-devel/fuckcc"
        ]
        config_map = {
            '._cfg0000_packages.db.critical': 'faa50df927223bb6de967e33179803b7',
            '._cfg0000_packages.db.system_mask': 'b7f536785e315f7c104c7185b0bfe608',
            '._cfg0000_packages.server.dep_blacklist.test': '8180f9e89d57f788e5b4bab05e30d447',
            '._cfg0000_packages.server.dep_rewrite.test': 'c31d66b7f03c725e586a6e22941b8082',
        }
        for file_path in files:
            updated_files = self.test_db._runConfigurationFilesUpdate(actions,
                [file_path])
            self.assertTrue(len(updated_files) == 1)
            updated_file = list(updated_files)[0]
            md5sum = entropy.tools.md5sum(updated_file)
            os.remove(updated_file)
            updated_name = os.path.basename(updated_file)
            self.assertEqual(config_map[updated_name], md5sum)

    def test_treeupdates_actions(self):
        self.assertEqual(self.test_db.listAllTreeUpdatesActions(), tuple())

        updates = (
            ('move media-libs/x264-svn media-libs/x264', '2020', '1210199116.46'),
            ('slotmove x11-libs/lesstif 2.1 0', '2020', '1210753863.16')
        )
        updates_out = (
            (1, 'test_suite', 'move media-libs/x264-svn media-libs/x264', '2020', '1210199116.46'),
            (2, 'test_suite', 'slotmove x11-libs/lesstif 2.1 0', '2020', '1210753863.16')
        )
        actions = tuple(sorted(['move media-libs/x264-svn media-libs/x264',
            'slotmove x11-libs/lesstif 2.1 0']))

        self.test_db.insertTreeUpdatesActions(updates, self.test_db_name)
        db_actions = self.test_db.retrieveTreeUpdatesActions(self.test_db_name)
        self.assertEqual(actions, db_actions)
        self.assertEqual(updates_out, self.test_db.listAllTreeUpdatesActions())

        self.test_db.removeTreeUpdatesActions(self.test_db_name)
        db_actions = self.test_db.retrieveTreeUpdatesActions(self.test_db_name)
        self.assertEqual(tuple(), db_actions)

    def test_contentsafety(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)

        self.assertEqual(data, db_data)
        path = "/usr/include/zconf.h"
        content_safety = self.test_db.searchContentSafety(path)
        self.assertEqual(content_safety, (
            {'package_id': 1,
             'sha256': data['content_safety'][path]['sha256'],
             'path': '/usr/include/zconf.h',
             'mtime': data['content_safety'][path]['mtime']},)
        )

    def test_needed(self):
        test_pkg1 = _misc.get_test_package()
        test_pkg2 = _misc.get_test_package4()
        for test_pkg in (test_pkg1, test_pkg2):
            data = self.Spm.extract_package_metadata(test_pkg)
            idpackage = self.test_db.addPackage(data)
            db_data = self.test_db.getPackageData(idpackage)

            _misc.clean_pkg_metadata(db_data)
            _misc.clean_pkg_metadata(data)
            self.assertEqual(data, db_data)

            db_needed = self.test_db.retrieveNeededLibraries(
                idpackage)
            self.assertEqual(db_needed, data['needed_libs'])

            db_needed = self.test_db.retrieveNeededLibraries(idpackage)
            self.assertEqual(db_needed, data['needed_libs'])

    def test_dependencies(self):
        test_pkg = _misc.get_test_package3()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

        pkg_deps = sorted(
            self.test_db.retrieveDependencies(
                idpackage, extended = True))
        orig_pkg_deps = sorted([
                ('=dev-libs/apr-1*', 0),
                ('dev-libs/openssl', 0),
                ('dev-libs/libpcre', 0),
                ('=dev-libs/apr-util-1*', 0),
                ('=dev-libs/apr-1*', 3),
                ('dev-libs/openssl', 3),
                ('dev-libs/libpcre', 3),
                ('=dev-libs/apr-util-1*', 3),
                ])

        self.assertEqual(pkg_deps, orig_pkg_deps)

    def test_use_dependencies(self):
        test_pkg = _misc.get_test_entropy_package6()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

        useflags = self.test_db.retrieveUseflags(idpackage)
        self.assertTrue("gtk" not in useflags)
        self.assertTrue("-gtk" in useflags)
        self.assertTrue("-kde" in useflags)
        self.assertTrue("-debug" in useflags)
        self.assertTrue("-examples" in useflags)

    def test_content(self):
        test_pkg = _misc.get_test_package3()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)

        self.assertEqual(data, db_data)
        content = self.test_db.retrieveContent(
            idpackage, extended = True, order_by="file")
        orig_content = (('/usr/sbin/ab2-ssl', 'sym'),
            ('/usr/sbin/logresolve2', 'sym'),
            ('/usr/sbin/log_server_status', 'obj'),
            ('/usr/sbin/checkgid2', 'sym'),
            ('/usr/sbin/htdbm', 'obj'),
            ('/usr/sbin/rotatelogs2', 'sym'),
            ('/usr/share/man/man1/htpasswd.1.bz2', 'obj'),
            ('/usr/sbin/ab-ssl', 'sym'),
            ('/usr/sbin/htcacheclean2', 'sym'),
            ('/usr/sbin/split-logfile2', 'sym'),
            ('/usr/share/man/man8', 'dir'),
            ('/usr/sbin/htcacheclean', 'obj'),
            ('/usr/sbin', 'dir'), ('/usr/sbin/ab', 'obj'),
            ('/usr/share/doc/apache-tools-2.2.11/CHANGES.bz2', 'obj'),
            ('/usr/sbin/htpasswd', 'obj'), ('/usr', 'dir'),
            ('/usr/bin/htpasswd', 'sym'),
            ('/usr/share/man/man1/htdigest.1.bz2', 'obj'),
            ('/usr/sbin/dbmmanage', 'obj'), ('/usr/share', 'dir'),
            ('/usr/share/man/man1', 'dir'), ('/usr/sbin/htdbm2', 'sym'),
            ('/usr/sbin/log_server_status2', 'sym'),
            ('/usr/share/man/man1/dbmmanage.1.bz2', 'obj'),
            ('/usr/share/man', 'dir'), ('/usr/sbin/htpasswd2', 'sym'),
            ('/usr/sbin/htdigest2', 'sym'), ('/usr/sbin/httxt2dbm2', 'sym'),
            ('/usr/bin', 'dir'), ('/usr/sbin/logresolve', 'obj'),
            ('/usr/share/doc', 'dir'), ('/usr/share/man/man8/ab.8.bz2', 'obj'),
            ('/usr/share/man/man8/logresolve.8.bz2', 'obj'),
            ('/usr/share/man/man8/htcacheclean.8.bz2', 'obj'),
            ('/usr/sbin/rotatelogs', 'obj'), ('/usr/sbin/checkgid', 'obj'),
            ('/usr/share/man/man1/htdbm.1.bz2', 'obj'),
            ('/usr/sbin/dbmmanage2', 'sym'), ('/usr/sbin/httxt2dbm', 'obj'),
            ('/usr/sbin/split-logfile', 'obj'),
            ('/usr/sbin/htdigest', 'obj'),
            ('/usr/share/doc/apache-tools-2.2.11', 'dir'),
            ('/usr/sbin/ab2', 'sym'),
            ('/usr/share/man/man8/rotatelogs.8.bz2', 'obj')
        )
        self.assertEqual(
            content,
            tuple(sorted(orig_content, key = lambda x: x[0])))

    def test_db_creation(self):
        self.assertTrue(isinstance(self.test_db, EntropyRepository))
        self.assertEqual(self.test_db_name, self.test_db.repository_id())
        self.assertTrue(self.test_db._doesTableExist('baseinfo'))
        self.assertTrue(self.test_db._doesTableExist('extrainfo'))

    def test_db_metadata_handling(self):

        test_entry = {
            const_convert_to_unicode("/path/to/foo", "utf-8"): \
                const_convert_to_unicode("dir", "utf-8"),
            const_convert_to_unicode("/path/to/foo/foo", "utf-8"): \
                const_convert_to_unicode("obj", "utf-8"),
        }

        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        data['content'].update(test_entry.copy())
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        test_pkg2 = _misc.get_test_package2()
        data2 = self.Spm.extract_package_metadata(test_pkg2)
        data2['content'].update(test_entry.copy())
        idpackage2 = self.test_db2.addPackage(data2)
        db_data2 = self.test_db2.getPackageData(idpackage2)

        cont_diff = self.test_db.contentDiff(idpackage, self.test_db2,
            idpackage2)

        for key in test_entry:
            try:
                self.assertTrue(key not in cont_diff)
            except AssertionError:
                print(key)
                raise

        py_diff = sorted([x for x in db_data['content'] if x not in \
            db_data2['content']])

        self.assertEqual(sorted(cont_diff), py_diff)

        orig_diff = ['/lib64', '/lib64/libz.so', '/lib64/libz.so.1',
            '/lib64/libz.so.1.2.3', '/usr/include', '/usr/include/zconf.h',
            '/usr/include/zlib.h', '/usr/lib64/libz.a',
            '/usr/lib64/libz.so', '/usr/share/doc/zlib-1.2.3-r1',
            '/usr/share/doc/zlib-1.2.3-r1/ChangeLog.bz2',
            '/usr/share/doc/zlib-1.2.3-r1/FAQ.bz2',
            '/usr/share/doc/zlib-1.2.3-r1/README.bz2',
            '/usr/share/doc/zlib-1.2.3-r1/algorithm.txt.bz2',
            '/usr/share/man', '/usr/share/man/man3',
            '/usr/share/man/man3/zlib.3.bz2'
        ]
        orig_diff = [const_convert_to_unicode(x, 'utf-8') for x in orig_diff]
        self.assertEqual(orig_diff, py_diff)

        versioning_data = self.test_db.getVersioningData(idpackage)
        dbverdata = (self.test_db.retrieveVersion(idpackage),
            self.test_db.retrieveTag(idpackage),
            self.test_db.retrieveRevision(idpackage),)
        self.assertEqual(versioning_data, dbverdata)

        strict_scope = self.test_db.getStrictScopeData(idpackage)
        dbverdata = (self.test_db.retrieveAtom(idpackage),
            self.test_db.retrieveSlot(idpackage),
            self.test_db.retrieveRevision(idpackage),)
        self.assertEqual(strict_scope, dbverdata)

        scope_data = self.test_db.getScopeData(idpackage)
        dbverdata = (
            self.test_db.retrieveAtom(idpackage),
            self.test_db.retrieveCategory(idpackage),
            self.test_db.retrieveName(idpackage),
            self.test_db.retrieveVersion(idpackage),
            self.test_db.retrieveSlot(idpackage),
            self.test_db.retrieveTag(idpackage),
            self.test_db.retrieveRevision(idpackage),
            self.test_db.retrieveBranch(idpackage),
            self.test_db.retrieveApi(idpackage),
        )
        self.assertEqual(scope_data, dbverdata)

        trigger_info = self.test_db.getTriggerData(idpackage)
        trigger_keys = ['version', 'etpapi', 'slot', 'cxxflags', 'cflags',
            'chost', 'atom', 'category', 'name', 'versiontag', 'content',
            'trigger', 'branch', 'spm_phases', 'revision']
        self.assertEqual(sorted(trigger_keys), sorted(trigger_info.keys()))

    def test_db_insert_compare_match_provide(self):
        test_pkg = _misc.get_test_entropy_package_provide()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

    def test_db_cache(self):
        test_pkg = _misc.get_test_entropy_package_provide()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)

        # enable cache
        self.test_db._caching = True
        key = data['category'] + "/" + data['name']

        from entropy.cache import EntropyCacher
        cacher = EntropyCacher()
        started = cacher.is_started()
        cacher.start()
        # avoid race conditions, unittest bug
        time.sleep(2)

        cached = self.test_db._EntropyRepositoryBase__atomMatchFetchCache(
            key, True, False, False, None, None, False, False, True)
        self.assertTrue(cached is None)

        # now store
        self.test_db._EntropyRepositoryBase__atomMatchStoreCache(
            key, True, False, False, None, None, False, False, True,
            result = (123, 0)
        )
        cacher.sync()

        cached = self.test_db._EntropyRepositoryBase__atomMatchFetchCache(
            key, True, False, False, None, None, False, False, True)
        self.assertEqual(cached, (123, 0))
        if not started:
            cacher.stop()

    def test_db_insert_compare_match(self):

        # insert/compare
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

        # match
        nf_match = (-1, 1)
        f_match = (1, 0)
        pkg_atom = _misc.get_test_package_atom()
        pkg_name = _misc.get_test_package_name()
        self.assertEqual(nf_match, self.test_db.atomMatch("slib"))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_name))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_atom))

        # test package masking
        masking_validation = \
            self.Client.ClientSettings()['masking_validation']['cache']
        f_match_mask = (1, self.test_db_name,)

        self._settings['live_packagemasking']['mask_matches'].add(
            f_match_mask)
        masking_validation.clear()
        self.assertEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

        self._settings['live_packagemasking']['mask_matches'].discard(
            f_match_mask)
        masking_validation.clear()
        self.assertNotEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

        # now test multimatch
        idpackage = self.test_db.addPackage(db_data)
        results, rc = self.test_db.atomMatch(pkg_name, multiMatch = True)
        self.assertEqual(2, len(results))
        self.assertTrue(isinstance(results, set))
        self.assertTrue(rc == 0)

        results, rc = self.test_db.atomMatch(pkg_name+"foo", multiMatch = True)
        self.assertEqual(0, len(results))
        self.assertTrue(isinstance(results, set))
        self.assertTrue(rc == 1)

    def test_db_insert_compare_match_utf(self):

        # insert/compare
        test_pkg = _misc.get_test_package2()
        data = self.Spm.extract_package_metadata(test_pkg)
        # Portage stores them this way
        unicode_msg = const_convert_to_unicode(
            "#248083).\n\n  06 Feb 2009; Ra\xc3\xbal Porcel")
        data['changelog'] = unicode_msg
        data['license'] = const_convert_to_unicode('GPL-2')
        data['licensedata'] = {
            const_convert_to_unicode('GPL-2'): unicode_msg,
        }
        data['content_safety'] = {
            unicode_msg: {
                'sha256': "abcdbbcdbcdbcdbcdbcdbcdbcbd",
                'mtime': 1024.0,
            }
        }
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

        # match
        nf_match = (-1, 1)
        f_match = (1, 0)
        pkg_atom = _misc.get_test_package_atom2()
        pkg_name = _misc.get_test_package_name2()
        self.assertEqual(nf_match, self.test_db.atomMatch("slib"))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_name))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_atom))

        # test package masking
        masking_validation = self.Client.ClientSettings(
            )['masking_validation']['cache']
        f_match_mask = (1, self.test_db_name,)

        self._settings['live_packagemasking']['mask_matches'].add(
            f_match_mask)
        masking_validation.clear()
        self.assertEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

        self._settings['live_packagemasking']['mask_matches'].discard(
            f_match_mask)
        masking_validation.clear()
        self.assertNotEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

    def test_db_insert_compare_match_utf2(self):

        # insert/compare
        test_pkg = _misc.get_test_package3()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

        # match
        nf_match = (-1, 1)
        f_match = (1, 0)
        pkg_atom = _misc.get_test_package_atom3()
        pkg_name = _misc.get_test_package_name3()
        self.assertEqual(nf_match, self.test_db.atomMatch("slib"))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_name))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_atom))

        # test package masking
        masking_validation = self.Client.ClientSettings(
            )['masking_validation']['cache']
        f_match_mask = (1, self.test_db_name,)

        self._settings['live_packagemasking']['mask_matches'].add(
            f_match_mask)
        masking_validation.clear()
        self.assertEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

        self._settings['live_packagemasking']['mask_matches'].discard(
            f_match_mask)
        masking_validation.clear()
        self.assertNotEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

    def test_db_insert_compare_match_mime(self):

        # insert/compare
        test_pkg = _misc.get_test_package4()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

        known_mime = set(['application/ogg', 'audio/x-oggflac', 'audio/x-mp3',
            'audio/x-pn-realaudio', 'audio/mpeg', 'application/x-ogm-audio',
            'audio/vorbis', 'video/x-ms-asf', 'audio/x-speex', 'audio/x-scpls',
            'audio/x-vorbis', 'audio/mpegurl', 'audio/aac', 'audio/x-ms-wma',
            'audio/ogg', 'audio/x-mpegurl', 'audio/mp4',
            'audio/vnd.rn-realaudio', 'audio/x-vorbis+ogg', 'audio/x-musepack',
            'audio/x-flac', 'audio/x-wav'])
        self.assertEqual(db_data['provided_mime'], known_mime)

        # match
        nf_match = (-1, 1)
        f_match = (1, 0)
        pkg_atom = _misc.get_test_package_atom4()
        pkg_name = _misc.get_test_package_name4()
        self.assertEqual(nf_match, self.test_db.atomMatch("slib"))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_name))
        self.assertEqual(f_match,
            self.test_db.atomMatch(pkg_atom))

        # test package masking
        masking_validation = self.Client.ClientSettings(
            )['masking_validation']['cache']
        f_match_mask = (1, self.test_db_name,)

        self._settings['live_packagemasking']['mask_matches'].add(
            f_match_mask)
        masking_validation.clear()
        self.assertEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

        self._settings['live_packagemasking']['mask_matches'].discard(
            f_match_mask)
        masking_validation.clear()
        self.assertNotEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

    def test_db_insert_compare_match_tag(self):

        # insert/compare
        test_pkg = _misc.get_test_entropy_package_tag()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(db_data)
        _misc.clean_pkg_metadata(data)
        self.assertEqual(data, db_data)

        # match
        f_match = (1, 0)

        for atom, pkg_id, branch in self.test_db.listAllPackages():
            pkg_key = entropy.dep.dep_getkey(atom)
            self.assertEqual(f_match, self.test_db.atomMatch(pkg_key))
            self.assertEqual(f_match, self.test_db.atomMatch(atom))
            self.assertEqual(f_match, self.test_db.atomMatch("~"+atom))

    def test_db_multithread(self):

        # insert/compare
        test_pkg = _misc.get_test_entropy_package_tag()
        data = self.Spm.extract_package_metadata(test_pkg)
        _misc.clean_pkg_metadata(data)

        def handle_pkg(xdata):
            idpackage = self.test_db.addPackage(xdata)
            db_data = self.test_db.getPackageData(idpackage)

            _misc.clean_pkg_metadata(db_data)
            self.assertEqual(xdata, db_data)

        t1 = ParallelTask(handle_pkg, data)
        t2 = ParallelTask(handle_pkg, data)
        t3 = ParallelTask(handle_pkg, data)
        t4 = ParallelTask(handle_pkg, data)
        t1.start()
        t2.start()
        t3.start()
        t4.start()

        t1.join()
        t2.join()
        t3.join()
        t4.join()

        cur_cache = self.test_db._cursor_pool().keys()
        self.assertTrue(len(cur_cache) > 0)
        self.test_db._cleanup_all()
        cur_cache = self.test_db._cursor_pool().keys()
        self.assertEqual(len(cur_cache), 0)

    def test_db_close_all(self):
        """
        This tests if EntropyRepository.close() really closes
        all the resources, including those allocated by the
        main thread.
        """

        test_pkg = _misc.get_test_entropy_package_tag()
        data = self.Spm.extract_package_metadata(test_pkg)
        _misc.clean_pkg_metadata(data)

        _tmp_data = {
            "path": None,
            "db": None,
            "T1": False,
            "T2": False,
            "T3": False,
        }

        def handle_pkg(_tmp_data, xdata):
            idpackage = self.test_db.addPackage(xdata)
            db_data = self.test_db.getPackageData(idpackage)

            _misc.clean_pkg_metadata(db_data)
            self.assertEqual(xdata, db_data)
            self.test_db.commit()
            fd, buf_file = const_mkstemp()
            os.close(fd)
            buf = open(buf_file, "wb")

            set_mute(True)
            self.test_db.exportRepository(buf)
            set_mute(False)

            buf.flush()
            buf.close()

            fd, buf_file_db = const_mkstemp()
            os.close(fd)
            self.test_db.importRepository(buf_file, buf_file_db)
            os.remove(buf_file)
            db = self.Client.open_generic_repository(buf_file_db)
            self.assertTrue(db is not None)
            pkg_ids = db.listAllPackageIds()
            self.assertTrue(1 in pkg_ids)
            _tmp_data['path'] = buf_file_db
            _tmp_data['db'] = db
            _tmp_data['T1'] = True

        def select_pkg(_tmp_data, t1):
            t1.join() # wait for t1 to finish
            pkg_ids = _tmp_data['db'].listAllPackageIds()
            self.assertTrue(1 in pkg_ids)
            self.assertTrue(len(pkg_ids) == 1)
            _tmp_data['T2'] = True

        def close_all(_tmp_data, t1, t2):
            t1.join()
            t2.join()

            _tmp_data['db']._cleanup_all(_cleanup_main_thread=False)
            with _tmp_data['db']._cursor_pool_mutex():
                cur_cache = _tmp_data['db']._cursor_pool().keys()
            self.assertEqual(len(cur_cache), 1) # just MainThread

            _tmp_data['db'].close()
            with _tmp_data['db']._cursor_pool_mutex():
                cur_cache = _tmp_data['db']._cursor_pool().keys()
            self.assertEqual(len(cur_cache), 0) # nothing left
            _tmp_data['T3'] = True

        t1 = ParallelTask(handle_pkg, _tmp_data, data)
        t1.name = "T1"
        t2 = ParallelTask(select_pkg, _tmp_data, t1)
        t2.name = "T2"
        t3 = ParallelTask(close_all, _tmp_data, t1, t2)
        t3.name = "T3"
        t1.start()
        t2.start()

        t1.join()
        pkg_ids = _tmp_data['db'].listAllPackageIds()

        t2.join()
        t3.start()
        t3.join()

        self.assertTrue(_tmp_data['T1'] and _tmp_data['T2'] \
                            and _tmp_data['T3'])

        self.assertTrue(1 in pkg_ids)
        self.assertTrue(len(pkg_ids) == 1)
        _tmp_data['db'].close()
        with _tmp_data['db']._cursor_pool_mutex():
            cur_cache = _tmp_data['db']._cursor_pool().keys()
        self.assertEqual(len(cur_cache), 0) # nothing left
        os.remove(_tmp_data['path'])

    def test_db_reverse_deps(self):

        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        test_pkg2 = _misc.get_test_package2()
        data2 = self.Spm.extract_package_metadata(test_pkg2)
        data['pkg_dependencies'] += ((
                _misc.get_test_package_atom2(),
                etpConst['dependency_type_ids']['rdepend_id']),)
        data2['pkg_dependencies'] += ((
                _misc.get_test_package_atom(),
                etpConst['dependency_type_ids']['rdepend_id']),)

        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(db_data)
        self.assertEqual(data, db_data)

        idpackage2 = self.test_db.addPackage(data2)
        db_data2 = self.test_db.getPackageData(idpackage2)

        _misc.clean_pkg_metadata(data2)
        _misc.clean_pkg_metadata(db_data2)
        self.assertEqual(data2, db_data2)

        rev_deps = self.test_db.retrieveReverseDependencies(idpackage)
        rev_deps2 = self.test_db.retrieveReverseDependencies(idpackage2)

        self.assertTrue(idpackage in rev_deps2)
        self.assertTrue(idpackage2 in rev_deps)
        rev_deps_t = self.test_db.retrieveReverseDependencies(idpackage,
            key_slot = True)
        self.assertEqual(rev_deps_t, (('app-dicts/aspell-es', '0'),))

        pkg_data = self.test_db.retrieveUnusedPackageIds()
        self.assertEqual(pkg_data, tuple())

    def test_similar(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(db_data)
        self.assertEqual(data, db_data)
        out = self.test_db.searchSimilarPackages(_misc.get_test_package_name())
        self.assertEqual(out, (1,))

    def test_search(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(db_data)
        self.assertEqual(data, db_data)

        out = self.test_db.searchPackages(_misc.get_test_package_name())
        self.assertEqual(out, (('sys-libs/zlib-1.2.3-r1', 1, '5'),))
        out = self.test_db.searchPackages(_misc.get_test_package_name(),
            slot = "0")
        self.assertEqual(out, (('sys-libs/zlib-1.2.3-r1', 1, '5'),))
        out = self.test_db.searchPackages(_misc.get_test_package_name(),
            slot = "0", just_id = True)
        self.assertEqual(out, (1,))

    def test_list_packages(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        out = self.test_db.listAllPackages()
        self.assertEqual(out, (('sys-libs/zlib-1.2.3-r1', 1, '5'),))

    def test_spmuids(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        out = self.test_db.listAllSpmUids()
        self.assertEqual(out, ((22331, 1),))

    def test_list_pkg_ids(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        out = self.test_db.listAllPackageIds(order_by="atom")
        self.assertEqual(out, (1,))

    def test_list_files(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        out = sorted(self.test_db.listAllFiles())
        self.assertEqual(out, sorted([
            '/lib64/libz.so', '/usr/share/doc/zlib-1.2.3-r1',
            '/usr/share/doc/zlib-1.2.3-r1/algorithm.txt.bz2',
            '/usr/share/doc/zlib-1.2.3-r1/FAQ.bz2',
            '/usr/share/doc/zlib-1.2.3-r1/ChangeLog.bz2',
            '/usr', '/usr/include', '/usr/lib64',
            '/usr/share/man/man3/zlib.3.bz2', '/usr/lib64/libz.a', '/lib64',
            '/usr/share', '/usr/share/doc/zlib-1.2.3-r1/README.bz2',
            '/usr/lib64/libz.so', '/usr/share/man', '/usr/include/zconf.h',
            '/lib64/libz.so.1.2.3', '/usr/include/zlib.h', '/usr/share/doc',
            '/usr/share/man/man3', '/lib64/libz.so.1'])
        )

    def test_list_categories(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        out = self.test_db.listAllCategories()
        self.assertEqual(out, frozenset(('sys-libs',)))

    def test_list_downloads(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        out = self.test_db.listAllDownloads()
        self.assertEqual(out, ('sys-libs:zlib-1.2.3-r1.334f75538e6eddde753d9a247609dd8b1123a541.tbz2',))

    def test_search_name(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(db_data)
        self.assertEqual(db_data, data)

        out = self.test_db.searchName(_misc.get_test_package_name())
        self.assertEqual(out, frozenset([('sys-libs/zlib-1.2.3-r1', 1)]))

    def test_db_indexes(self):
        self.test_db.createAllIndexes()

    def test_db_import_export(self):

        test_pkg = _misc.get_test_package2()
        data = self.Spm.extract_package_metadata(test_pkg)
        # Portage stores them this way
        data['changelog'] = const_convert_to_unicode(
            "#248083).\n\n  06 Feb 2009; Ra\xc3\xbal Porcel")
        data['license'] = const_convert_to_unicode('GPL-2')
        data['licensedata'] = {
            const_convert_to_unicode('GPL-2'): \
                const_convert_to_unicode(
                    "#248083).\n\n  06 Feb 2009; Ra\xc3\xbal Porcel"),
        }
        idpackage = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(db_data)
        assert set(data.keys()) == set(db_data.keys())
        for k, v in data.items():
            if v != db_data[k]:
                print(k, v, "vs", db_data[k])
        self.assertEqual(data, db_data)

        set_mute(True)

        # export
        fd, buf_file = const_mkstemp()
        os.close(fd)
        buf = open(buf_file, "wb")
        self.test_db.exportRepository(buf)
        buf.flush()
        buf.close()

        fd, new_db_path = const_mkstemp()
        os.close(fd)
        self.test_db.importRepository(buf_file, new_db_path)
        new_db = self.Client.open_generic_repository(new_db_path)
        new_db_data = new_db.getPackageData(idpackage)

        _misc.clean_pkg_metadata(new_db_data)
        new_db.close()
        set_mute(True)
        self.assertEqual(new_db_data, db_data)
        os.remove(buf_file)
        os.remove(new_db_path)

    def test_use_defaults(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        key, slot = self.test_db.retrieveKeySlot(idpackage)
        valid_test_deps = [
            "%s[%s(+)]" % (key, "doesntexistforsure"),
            "%s[-%s(-)]" % (key, "doesntexistforsure"),
            "%s[%s(+)]" % (key, "kernel_linux"),
            "%s[%s(-)]" % (key, "kernel_linux"),
        ]
        invalid_test_deps = [
            "%s[%s(-)]" % (key, "doesntexistforsure"),
            "%s[-%s(+)]" % (key, "kernel_linux"),
            "%s[-%s(+)]" % (key, "doesntexistforsure"),
            "%s[-%s(-)]" % (key, "kernel_linux"),
        ]
        for dep in valid_test_deps:
            self.assertEqual((1, 0), self.test_db.atomMatch(dep))
        for dep in invalid_test_deps:
            self.assertEqual((-1, 1), self.test_db.atomMatch(dep))

    def test_db_package_sets(self):

        set_name = 'my_test_set'
        set_deps = ["app-foo/foo", "app-pling/plong", "media-foo/ajez"]
        set_name2 = 'my_test_set2'
        set_deps2 = ["app-foo/foo2", "app-pling/plong2", "media-foo/ajez2"]
        pkgsets = {
            set_name: set(set_deps),
            set_name2: set(set_deps2),
        }
        self.test_db.insertPackageSets(pkgsets)
        self.assertEqual(self.test_db.retrievePackageSets(), pkgsets)
        set_search = self.test_db.searchSets(set_name2)
        self.assertEqual(set([set_name2]), set_search)

    def test_db_license_data_str_insert(self):
        lic_txt = const_convert_to_rawstring('[3]\xab foo\n\n', 'utf-8')
        lic_name = const_convert_to_unicode('CCPL-Attribution-2.0')
        lic_data = {lic_name: lic_txt}
        self.test_db._insertLicenses(lic_data)
        db_lic_txt = self.test_db.retrieveLicenseText(lic_name)
        self.assertEqual(db_lic_txt, lic_txt)

    def test_settings(self):
        self.assertRaises(KeyError, self.test_db.getSetting, "fuck")
        self.test_db._setSetting("something_cool", "abcdef\nabcdef")
        self.assertEqual(self.test_db.getSetting("something_cool"),
            "abcdef\nabcdef")

    def test_new_entropyrepository_schema(self):
        test_pkg = _misc.get_test_package2()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = self.test_db.addPackage(data)
        old_data = self.test_db.getPackageData(idpackage)
        old_base_data = self.test_db.getBaseData(idpackage)
        old_cats = self.test_db.listAllCategories()

        test_db = self.__open_test_db(":memory:")
        idpackage = test_db.addPackage(data)
        new_data = test_db.getPackageData(idpackage)
        new_base_data = test_db.getBaseData(idpackage)
        new_cats = test_db.listAllCategories()

        self.assertTrue(test_db._isBaseinfoExtrainfo2010())
        self.assertEqual(old_data, new_data)
        self.assertEqual(old_base_data, new_base_data)
        self.assertEqual(old_cats, new_cats)

        test_db.close()

    def test_preserved_libs(self):
        data = self.test_db.listAllPreservedLibraries()
        self.assertEqual(data, tuple())

        atom = "app-foo/bar-1.2.3"
        fake_data = [
            ("libfoo.so.3", 2, "/usr/lib64/libfoo.so.3", atom),
            ("libfoo.so.3", 2, "/usr/lib64/libfoo.so.3.0.0", atom),
            ("libfoo.so.3", 2, "/usr/lib64/libfoo.so", atom),
            ("libbar.so.10", 2, "/usr/lib64/libbar.so.10", atom),
            ("libbar.so.10", 2, "/usr/lib64/libbar.so", atom),
            ("libbar.so.10", 2, "/usr/lib64/libbar.so.10.0.0", atom),
        ]
        for entry in fake_data:
            self.test_db.insertPreservedLibrary(*entry)

        # test that insert order equals list
        data = self.test_db.listAllPreservedLibraries()
        self.assertEqual(tuple(data), tuple(fake_data))

        grouped = {}
        for lib, elfclass, path, _atom in data:
            obj = grouped.setdefault((lib, elfclass), [])
            obj.append(path)

        # make sure that retrieve works as intended
        for (lib, elfclass), paths in grouped.items():
            out_paths = self.test_db.retrievePreservedLibraries(
                lib, elfclass)
            self.assertEqual(sorted(out_paths), sorted(paths))

        # test removal
        count = len(data)
        for lib, elfclass, path, _atom in data:
            self.test_db.removePreservedLibrary(lib, elfclass, path)
            count -= 1
            current_preserved_libs = self.test_db.listAllPreservedLibraries()
            self.assertEqual(len(current_preserved_libs), count)
            self.assertTrue((lib, elfclass, path) not in current_preserved_libs)

        data = self.test_db.listAllPreservedLibraries()
        self.assertEqual(data, tuple())

    def _test_repository_locking(self, test_db):

        with test_db.shared():
            self.assertRaises(RuntimeError, test_db.try_acquire_exclusive)

        with test_db.exclusive():
            opaque = test_db.try_acquire_shared()
            self.assertNotEqual(opaque, None)
            test_db.release_shared(opaque)

        opaque_shared = test_db.try_acquire_shared()
        self.assert_(opaque_shared is not None)

        self.assertRaises(RuntimeError, test_db.try_acquire_exclusive)

        test_db.release_shared(opaque_shared)

        # test reentrancy
        opaque_exclusive = test_db.try_acquire_exclusive()
        self.assert_(opaque_exclusive is not None)

        opaque_exclusive2 = test_db.try_acquire_exclusive()
        self.assert_(opaque_exclusive2 is not None)

        self.assert_(opaque_exclusive._file_lock_setup() is
                     opaque_exclusive2._file_lock_setup())

        # test reference counting
        self.assertEquals(
            2,
            opaque_exclusive._file_lock_setup()['count'])

        test_db.release_exclusive(opaque_exclusive)

        self.assertEquals(
            1,
            opaque_exclusive._file_lock_setup()['count'])

        test_db.release_exclusive(opaque_exclusive2)

        self.assertEquals(
            0,
            opaque_exclusive._file_lock_setup()['count'])

        # test that refcount doesn't go below zero
        self.assertRaises(
            RuntimeError, test_db.release_exclusive, opaque_exclusive)

        self.assertEquals(
            0,
            opaque_exclusive._file_lock_setup()['count'])

        opaque_exclusive = test_db.try_acquire_exclusive()
        self.assert_(opaque_exclusive is not None)

        self.assertRaises(RuntimeError, test_db.release_shared,
                          opaque_exclusive)

        test_db.release_exclusive(opaque_exclusive)

    def test_locking_file(self):

        fd, db_file = const_mkstemp()
        os.close(fd)
        test_db = None

        try:
            test_db = self.Client.open_generic_repository(db_file)
            test_db.initializeRepository()

            return self._test_repository_locking(test_db)

        finally:
            if test_db is not None:
                test_db.close()
            os.remove(db_file)

    def test_locking_memory(self):
        self.assert_(self.test_db._is_memory())
        return self._test_repository_locking(self.test_db)

    def test_direct_access(self):
        local = self.test_db._tls

        self.assertEquals(self.test_db.directed(), False)

        counter = getattr(local, "_EntropyRepositoryCacheCounter", "foo")
        self.assertEquals(counter, "foo")

        with self.test_db.direct():
            self.assertEquals(self.test_db.directed(), True)

        counter = local._EntropyRepositoryCacheCounter
        self.assertEquals(counter, 0)

        self.assertEquals(self.test_db.directed(), False)

        with self.test_db.direct():

            counter = local._EntropyRepositoryCacheCounter
            self.assertEquals(counter, 1)

            with self.test_db.direct():
                counter = local._EntropyRepositoryCacheCounter
                self.assertEquals(counter, 2)

            counter = local._EntropyRepositoryCacheCounter
            self.assertEquals(counter, 1)

        counter = local._EntropyRepositoryCacheCounter
        self.assertEquals(counter, 0)

        self.test_db._direct_enabled = True
        self.assertEquals(self.test_db.directed(), True)

        self.test_db._direct_enabled = False
        self.assertEquals(self.test_db.directed(), False)

        with self.test_db.direct():
            opaque = self.test_db.try_acquire_exclusive()
            self.assertTrue(opaque is not None)
            self.assertEquals(opaque.directed(), True)

            opaque_shared = self.test_db.try_acquire_shared()
            self.assertTrue(opaque_shared is not None)
            self.assertEquals(opaque_shared.directed(), True)

            opaque_exclusive = self.test_db.try_acquire_exclusive()
            self.assertTrue(opaque_exclusive is not None)
            self.assertEquals(opaque_exclusive.directed(), True)
            self.assertEquals(self.test_db.directed(), True)

            self.assertRaises(
                RuntimeError,
                self.test_db.release_shared, opaque_exclusive)
            self.test_db.release_exclusive(opaque_exclusive)
            self.assertEquals(self.test_db.directed(), True)

            self.assertRaises(
                RuntimeError,
                self.test_db.release_exclusive, opaque_shared)
            self.test_db.release_shared(opaque_shared)
            self.assertEquals(self.test_db.directed(), True)

            self.assertRaises(
                RuntimeError,
                self.test_db.release_shared, opaque)
            self.test_db.release_exclusive(opaque)
            self.assertEquals(self.test_db.directed(), True)


if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
