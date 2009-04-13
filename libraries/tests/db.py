#!/usr/bin/env python

import unittest
import os
from entropy.client.interfaces import Client
from entropy.db import LocalRepository

class LocalRepositoryTest(unittest.TestCase):

    def setUp(self):
        self.Client = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)

    def tearDown(self):
        """
        tearDown is run after each test
        """
        pass

    def test_db_creation(self):
        dbname = 'test_suite'
        mdb = self.Client.open_memory_database(dbname = dbname)
        self.assert_(isinstance(mdb,LocalRepository))
        self.assertEqual(dbname,mdb.dbname)
        self.assert_(mdb.doesTableExist('baseinfo'))
        self.assert_(mdb.doesTableExist('extrainfo'))
        mdb.closeDB()

if __name__ == '__main__':
    unittest.main()
