# -*- coding: utf-8 -*-
import sys
import unittest
import os
from entropy.client.interfaces import Client
from entropy.db import LocalRepository
import _misc

class LocalRepositoryTest(unittest.TestCase):

    def setUp(self):
        self.Client = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)
        self.test_db_name = "test_suite"
        self.test_db = self.__open_test_db()

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()
        self.test_db.closeDB()

    def __open_test_db(self):
        return self.Client.open_memory_database(dbname = self.test_db_name)

    def test_db_creation(self):
        self.assert_(isinstance(self.test_db,LocalRepository))
        self.assertEqual(self.test_db_name,self.test_db.dbname)
        self.assert_(self.test_db.doesTableExist('baseinfo'))
        self.assert_(self.test_db.doesTableExist('extrainfo'))

    def test_db_insert_compare_match(self):

        # insert/compare
        test_pkg = _misc.get_test_package()
        data = self.Client.extract_pkg_metadata(test_pkg, silent = True)
        idpackage, rev, new_data = self.test_db.handlePackage(data)
        db_data = self.test_db.getPackageData(idpackage)
        self.assertEqual(new_data, db_data)

        # match
        nf_match = (-1, 1)
        f_match = (1, 0)
        self.assertEqual(nf_match, self.test_db.atomMatch("slib"))
        self.assertEqual(f_match,
            self.test_db.atomMatch(_misc.get_test_package_name()))
        self.assertEqual(f_match,
            self.test_db.atomMatch(_misc.get_test_package_atom()))


if __name__ == '__main__':
    unittest.main()
