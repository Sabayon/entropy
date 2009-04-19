# -*- coding: utf-8 -*-
import sys
import unittest
import os
from entropy.client.interfaces import Client
from entropy.const import etpConst
from entropy.core import SystemSettings
from entropy.db import LocalRepository
import _misc

class LocalRepositoryTest(unittest.TestCase):

    def setUp(self):
        self.Client = Client(noclientdb = 2, indexing = False, xcache = False,
            repo_validation = False)
        self.SystemSettings = SystemSettings()

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

if __name__ == '__main__':
    unittest.main()
