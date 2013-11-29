# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import entropy.qa
from entropy.output import TextInterface
import entropy.tools
import tests._misc as _misc
import tempfile

class QATest(unittest.TestCase):

    def setUp(self):
        text = TextInterface()
        self.QA = entropy.qa.QAInterface()

    def test_package_qa(self):
        pkgs = [_misc.get_test_entropy_package4(),
            _misc.get_test_entropy_package3(),
            _misc.get_test_entropy_package2(),
            _misc.get_test_entropy_package()
        ]
        for pkg in pkgs:
            self.assertTrue(self.QA.entropy_package_checks(pkg))

if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
