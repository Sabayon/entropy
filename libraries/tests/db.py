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

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def __open_test_db(self):
        return self.Client.open_memory_database(dbname = self.test_db_name)

    def test_db_creation(self):
        mdb = self.__open_test_db()
        self.assert_(isinstance(mdb,LocalRepository))
        self.assertEqual(self.test_db_name,mdb.dbname)
        self.assert_(mdb.doesTableExist('baseinfo'))
        self.assert_(mdb.doesTableExist('extrainfo'))
        mdb.closeDB()

    def test_db_insert_and_match(self):
        test_pkg = _misc.get_test_package()
        data = self.Client.extract_pkg_metadata(test_pkg, silent = True)
        mdb = self.__open_test_db()
        idpackage, rev, new_data = mdb.handlePackage(data)
        db_data = mdb.getPackageData(idpackage, trigger_unicode = True)
        mdb.closeDB()
        self.assertEqual(new_data, db_data)

if __name__ == '__main__':
    unittest.main()
