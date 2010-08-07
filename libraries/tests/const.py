# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, 'client')
sys.path.insert(0, '../../client')
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import tests._misc as _misc
from entropy.const import const_drop_privileges, const_regain_privileges
from entropy.exceptions import SecurityError

class ConstTest(unittest.TestCase):

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def test_privileges(self):

        self.assert_(os.getuid() == 0)
        self.assert_(os.getgid() == 0)
        const_drop_privileges()
        self.assert_(os.getuid() != 0)
        self.assert_(os.getgid() != 0)

        const_regain_privileges()
        self.assert_(os.getuid() == 0)
        self.assert_(os.getgid() == 0)

        const_drop_privileges()
        self.assert_(os.getuid() != 0)
        self.assert_(os.getgid() != 0)
        const_drop_privileges()
        self.assert_(os.getuid() != 0)
        self.assert_(os.getgid() != 0)
        const_regain_privileges()
        self.assert_(os.getuid() == 0)
        self.assert_(os.getgid() == 0)

if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
    entropy.tools.kill_threads()
    raise SystemExit(0)
