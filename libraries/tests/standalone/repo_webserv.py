# -*- coding: utf-8 -*-
import sys
import os
import tempfile
import unittest
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from entropy.client.interfaces import Client
from entropy.services.client import WebService
from entropy.client.services.interfaces import Document, DocumentFactory, \
    DocumentList, ClientWebService
from entropy.const import etpConst, etpUi, const_convert_to_rawstring, \
    const_convert_to_unicode, const_get_stringtype
import entropy.tools
import tests._misc as _misc
from entropy.core.settings.base import SystemSettings


class EntropyWebServicesTest(unittest.TestCase):

    def __init__(self, *args):
        unittest.TestCase.__init__(self, *args)
        self._repository_id = \
            SystemSettings()['repositories']['default_repository']

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()
        self._entropy = Client(installed_repo = -1, indexing = False,
            xcache = False, repo_validation = False)
        self._factory = self._entropy.RepositoryWebServices()

    def __open_test_db(self, tmp_path):
        return self._entropy.open_temp_repository(name = "test_suite",
            temp_file = tmp_path)

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
        self._entropy.destroy()
        self._entropy.shutdown()

    def test_get_package_ids(self):
        webserv = self._factory.new(self._repository_id)
        package_ids = webserv.get_package_ids()
        self.assertTrue(package_ids)
        self.assertTrue(isinstance(package_ids, list))
        self.assertTrue(isinstance(package_ids[0], int))
        return package_ids

    def test_get_revision(self):
        webserv = self._factory.new(self._repository_id)
        revision = webserv.get_revision()
        self.assertTrue(revision)
        self.assertTrue(isinstance(revision, const_get_stringtype()))

    def test_service_available(self):
        webserv = self._factory.new(self._repository_id)
        self.assertEqual(webserv.service_available(), True)

    def test_get_repository_metadata(self):
        webserv = self._factory.new(self._repository_id)
        repo_meta = webserv.get_repository_metadata()
        self.assertTrue(isinstance(repo_meta, dict))
        self.assertTrue("sets" in repo_meta)
        self.assertTrue(isinstance(repo_meta['sets'], dict))
        self.assertTrue(isinstance(repo_meta['treeupdates_actions'], list))
        self.assertTrue("treeupdates_actions" in repo_meta)
        self.assertTrue(isinstance(repo_meta['treeupdates_actions'], list))
        self.assertTrue("treeupdates_digest" in repo_meta)
        self.assertTrue(isinstance(repo_meta['treeupdates_digest'], 
            const_get_stringtype()))
        self.assertTrue("revision" in repo_meta)
        self.assertTrue(isinstance(repo_meta['revision'], const_get_stringtype()))
        self.assertTrue("checksum" in repo_meta)
        self.assertTrue(isinstance(repo_meta['checksum'], const_get_stringtype()))

    def test_get_packages_metadata(self):
        package_ids = self.test_get_package_ids()
        self.assertTrue(package_ids)
        self.assertTrue(isinstance(package_ids, list))
        self.assertTrue(isinstance(package_ids[0], int))
        # get a reasonable chunk
        pkg_chunks = package_ids[:5]
        webserv = self._factory.new(self._repository_id)
        pkg_meta = webserv.get_packages_metadata(pkg_chunks)
        self.assertTrue(pkg_meta)
        self.assertTrue(isinstance(pkg_meta, dict))
        for pkg_id in pkg_meta.keys():
            self.assertTrue(isinstance(pkg_meta[pkg_id], dict))

        def _convert_t(obj):
            if isinstance(obj, (tuple, list, set, frozenset)):
                return sorted([_convert_t(x) for x in obj])
            elif isinstance(obj, dict):
                new_d = {}
                for k, v in obj.items():
                    new_d[k] = _convert_t(v)
                return new_d
            return obj

        test_repo = self.__open_test_db(":memory:")
        got_package_ids = []
        for package_id, pkg_data in pkg_meta.items():
            got_package_ids.append(package_id)
            repo_package_id = test_repo.addPackage(pkg_data)
            repo_pkg_data = test_repo.getPackageData(repo_package_id,
                content_insert_formatted = True,
                get_content = False, get_changelog = False)
            self.assertEqual(sorted(pkg_data.keys()),
                sorted(repo_pkg_data.keys()))
            for key in repo_pkg_data.keys():
                self.assertEqual(_convert_t(repo_pkg_data[key]),
                    _convert_t(pkg_data[key]))
        self.assertEqual(sorted(got_package_ids), sorted(pkg_chunks))

        test_repo.close()

if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
    entropy.tools.kill_threads()
    raise SystemExit(0)
