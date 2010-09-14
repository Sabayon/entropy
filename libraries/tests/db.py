# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import os
import tempfile
from entropy.client.interfaces import Client
from entropy.const import etpConst, etpUi, const_convert_to_unicode, \
    const_convert_to_rawstring
from entropy.core.settings.base import SystemSettings
from entropy.misc import ParallelTask
from entropy.db import EntropyRepository
import tests._misc as _misc

import entropy.dep
import entropy.tools

class EntropyRepositoryTest(unittest.TestCase):

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()
        self.Client = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)
        self.Spm = self.Client.Spm()
        self.test_db_name = "%s_test_suite" % (etpConst['dbnamerepoprefix'],)
        self.client_sysset_plugin_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        self.test_db = self.__open_test_db(":memory:")
        # GenericRepository supports package masking if this property is set
        self.test_db.enable_mask_filter = True
        self.test_db2 = self.__open_test_db(":memory:")
        # GenericRepository supports package masking if this property is set
        self.test_db2.enable_mask_filter = True
        self._settings = SystemSettings()

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()
        self.test_db.closeDB()
        self.test_db2.closeDB()
        self.Client.shutdown()

    def __open_test_db(self, tmp_path):
        return self.Client.open_temp_repository(dbname = self.test_db_name,
            temp_file = tmp_path)

    def test_db_clearcache(self):
        self.test_db.clearCache()

    def test_treeupdates_actions(self):
        self.assertEqual(self.test_db.listAllTreeUpdatesActions(), tuple())

        updates = (
            ('move media-libs/x264-svn media-libs/x264', '2020', '1210199116.46'),
            ('slotmove x11-libs/lesstif 2.1 0', '2020', '1210753863.16')
        )
        updates_out = (
            (1, 'repo__test_suite', 'move media-libs/x264-svn media-libs/x264', '2020', '1210199116.46'),
            (2, 'repo__test_suite', 'slotmove x11-libs/lesstif 2.1 0', '2020', '1210753863.16')
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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(data, db_data)
        content_safety = self.test_db.searchContentSafety("/usr/include/zconf.h")
        self.assertEqual(content_safety, (
            {'package_id': 1,
             'sha256': '2969cdfba8290da429a6cde4d145e627beb839deca14578c2a430212cbaf91fb',
             'path': '/usr/include/zconf.h',
             'mtime': 1276241305.0},)
        )

    def test_needed(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(data, db_data)
        db_needed = self.test_db.retrieveNeeded(idpackage, extended = True)
        self.assertEqual(db_needed, data['needed'])
        db_needed = self.test_db.retrieveNeeded(idpackage)
        self.assertEqual(db_needed, tuple((lib for lib, elf_c in data['needed'])))

    def test_dependencies(self):
        test_pkg = _misc.get_test_package3()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(data, db_data)
        pkg_deps = self.test_db.retrieveDependencies(idpackage, extended = True)
        orig_pkg_deps = (('=dev-libs/apr-1*', 0),
            ('dev-libs/openssl', 0), ('dev-libs/libpcre', 0),
            ('=dev-libs/apr-util-1*', 0))
        self.assertEqual(pkg_deps, orig_pkg_deps)

    def test_content(self):
        test_pkg = _misc.get_test_package3()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(data, db_data)
        content = self.test_db.retrieveContent(idpackage, extended = True)
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
        self.assertEqual(content, orig_content)

    def test_db_creation(self):
        self.assert_(isinstance(self.test_db, EntropyRepository))
        self.assertEqual(self.test_db_name, self.test_db.reponame)
        self.assert_(self.test_db._doesTableExist('baseinfo'))
        self.assert_(self.test_db._doesTableExist('extrainfo'))

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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)

        test_pkg2 = _misc.get_test_package2()
        data2 = self.Spm.extract_package_metadata(test_pkg2)
        data2['content'].update(test_entry.copy())
        idpackage2, rev2, new_data2 = self.test_db2.addPackage(data2)
        db_data2 = self.test_db2.getPackageData(idpackage2)

        cont_diff = self.test_db.contentDiff(idpackage, self.test_db2,
            idpackage2)

        for key in test_entry:
            try:
                self.assert_(key not in cont_diff)
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
        trigger_keys = ['version', 'etpapi', 'cxxflags', 'cflags',
            'chost', 'atom', 'category', 'name', 'versiontag', 'content',
            'trigger', 'branch', 'spm_phases', 'revision']
        self.assertEqual(sorted(trigger_keys), sorted(trigger_info.keys()))

    def test_db_insert_compare_match_provide(self):
        test_pkg = _misc.get_test_entropy_package_provide()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

    def test_db_cache(self):
        test_pkg = _misc.get_test_entropy_package_provide()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)

        # enable cache
        self.test_db.xcache = True
        key = new_data['category'] + "/" + new_data['name']

        from entropy.cache import EntropyCacher
        cacher = EntropyCacher()
        started = cacher.is_started()
        cacher.start()

        cached = self.test_db._EntropyRepositoryBase__atomMatchFetchCache(
            key, True, False, False, None, None, False, False, True)
        self.assert_(cached is None)

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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

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
        plug_id = self.client_sysset_plugin_id
        masking_validation = \
            self._settings[plug_id]['masking_validation']['cache']
        f_match_mask = (1, 
            self.test_db_name[len(etpConst['dbnamerepoprefix']):],)

        self._settings['live_packagemasking']['mask_matches'].add(
            f_match_mask)
        masking_validation.clear()
        self.assertEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

        self._settings['live_packagemasking']['mask_matches'].discard(
            f_match_mask)
        masking_validation.clear()
        self.assertNotEqual((-1, 1), self.test_db.atomMatch(pkg_atom))

        # now test multimatch
        idpackage, rev, new_data = self.test_db.addPackage(db_data)
        results, rc = self.test_db.atomMatch(pkg_name, multiMatch = True)
        self.assertEqual(2, len(results))
        self.assert_(isinstance(results, set))
        self.assert_(rc == 0)

        results, rc = self.test_db.atomMatch(pkg_name+"foo", multiMatch = True)
        self.assertEqual(0, len(results))
        self.assert_(isinstance(results, set))
        self.assert_(rc == 1)

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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)
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
        plug_id = self.client_sysset_plugin_id
        masking_validation = \
            self._settings[plug_id]['masking_validation']['cache']
        f_match_mask = (1, 
            self.test_db_name[len(etpConst['dbnamerepoprefix']):],)

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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

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
        plug_id = self.client_sysset_plugin_id
        masking_validation = \
            self._settings[plug_id]['masking_validation']['cache']
        f_match_mask = (1, 
            self.test_db_name[len(etpConst['dbnamerepoprefix']):],)

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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

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
        plug_id = self.client_sysset_plugin_id
        masking_validation = \
            self._settings[plug_id]['masking_validation']['cache']
        f_match_mask = (1, 
            self.test_db_name[len(etpConst['dbnamerepoprefix']):],)

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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

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

        def handle_pkg(xdata):
            idpackage, rev, new_data = self.test_db.addPackage(xdata)
            db_data = self.test_db.getPackageData(idpackage)
            self.assertEqual(new_data, db_data)

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

        cur_cache = self.test_db._EntropyRepository__cursor_cache.keys()
        self.assert_(len(cur_cache) > 0)
        self.test_db._cleanup_stale_cur_conn(kill_all = True)
        cur_cache = self.test_db._EntropyRepository__cursor_cache.keys()
        self.assertEqual(len(cur_cache), 0)

    def test_db_reverse_deps(self):

        # insert/compare
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        test_pkg2 = _misc.get_test_package2()
        data2 = self.Spm.extract_package_metadata(test_pkg2)
        data['dependencies'][_misc.get_test_package_atom2()] = \
            etpConst['dependency_type_ids']['rdepend_id']
        data2['dependencies'][_misc.get_test_package_atom()] = \
            etpConst['dependency_type_ids']['rdepend_id']

        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

        idpackage2, rev, new_data2 = self.test_db.addPackage(data2)
        db_data2 = self.test_db.getPackageData(idpackage2)
        self.assertEqual(new_data2, db_data2)

        rev_deps = self.test_db.retrieveReverseDependencies(idpackage)
        rev_deps2 = self.test_db.retrieveReverseDependencies(idpackage2)

        self.assert_(idpackage in rev_deps2)
        self.assert_(idpackage2 in rev_deps)
        rev_deps_t = self.test_db.retrieveReverseDependencies(idpackage,
            key_slot = True)
        self.assertEqual(rev_deps_t, (('app-dicts/aspell-es', '0'),))

        pkg_data = self.test_db.retrieveUnusedPackageIds()
        self.assertEqual(pkg_data, tuple())

    def test_similar(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        self.assertEqual(new_data, data)
        out = self.test_db.searchSimilarPackages(_misc.get_test_package_name())
        self.assertEqual(out, (1,))

    def test_search(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        self.assertEqual(new_data, data)
        out = self.test_db.searchPackages(_misc.get_test_package_name())
        self.assertEqual(out, (('sys-libs/zlib-1.2.3-r1', 1, '5'),))

    def test_list_packages(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        out = self.test_db.listAllPackages()
        self.assertEqual(out, (('sys-libs/zlib-1.2.3-r1', 1, '5'),))

    def test_spmuids(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        out = self.test_db.listAllSpmUids()
        self.assertEqual(out, ((22331, 1),))

    def test_list_pkg_ids(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        out = self.test_db.listAllPackageIds(order_by="atom")
        self.assertEqual(out, (1,))

    def test_list_files(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        out = self.test_db.listAllFiles()
        self.assertEqual(out, (
            '/lib64/libz.so', '/usr/share/doc/zlib-1.2.3-r1',
            '/usr/share/doc/zlib-1.2.3-r1/algorithm.txt.bz2',
            '/usr/share/doc/zlib-1.2.3-r1/FAQ.bz2',
            '/usr/share/doc/zlib-1.2.3-r1/ChangeLog.bz2',
            '/usr', '/usr/include', '/usr/lib64',
            '/usr/share/man/man3/zlib.3.bz2', '/usr/lib64/libz.a', '/lib64',
            '/usr/share', '/usr/share/doc/zlib-1.2.3-r1/README.bz2',
            '/usr/lib64/libz.so', '/usr/share/man', '/usr/include/zconf.h',
            '/lib64/libz.so.1.2.3', '/usr/include/zlib.h', '/usr/share/doc',
            '/usr/share/man/man3', '/lib64/libz.so.1')
        )

    def test_list_categories(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        out = self.test_db.listAllCategories()
        self.assertEqual(out, ((1, 'sys-libs'),))

    def test_list_downloads(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        out = self.test_db.listAllDownloads()
        self.assertEqual(out, ('sys-libs:zlib-1.2.3-r1.tbz2',))

    def test_search_name(self):
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage, rev, new_data = self.test_db.addPackage(data)
        self.assertEqual(new_data, data)
        out = self.test_db.searchName(_misc.get_test_package_name())
        self.assertEqual(out, (('sys-libs/zlib-1.2.3-r1', 1),))

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
        idpackage, rev, new_data = self.test_db.addPackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

        etpUi['mute'] = True

        # export
        fd, buf_file = tempfile.mkstemp()
        os.close(fd)
        buf = open(buf_file, "wb")
        self.test_db.exportRepository(buf)
        buf.flush()
        buf.close()

        fd, new_db_path = tempfile.mkstemp()
        os.close(fd)
        self.test_db.importRepository(buf_file, new_db_path)
        new_db = self.Client.open_generic_repository(new_db_path)
        new_db_data = new_db.getPackageData(idpackage)
        new_db.closeDB()
        etpUi['mute'] = False
        self.assertEqual(new_db_data, db_data)
        os.remove(buf_file)
        os.remove(new_db_path)


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

if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
    entropy.tools.kill_threads()
    raise SystemExit(0)
