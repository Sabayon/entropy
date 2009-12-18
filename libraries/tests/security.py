# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'client')
sys.path.insert(0, '../../client')
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import os
import unittest
import tempfile
import shutil
from entropy.security import Repository
import tests._misc as _misc

class SecurityTest(unittest.TestCase):

    def setUp(self):
        """
        NOTE: this requires gnupg as test-dependency.
        """
        self._gpg_home = tempfile.mkdtemp()
        Repository.GPG_HOME = self._gpg_home
        self._repository = Repository()
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()

    def tearDown(self):
        """
        tearDown is run after each test
        """
        del self._repository
        shutil.rmtree(self._gpg_home, True)
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def test_gpg_handling(self):

        # available keys should be empty
        self.assertEqual(self._repository.get_keys(), {})

        # now fill
        self._repository.create_keypair("foo.org", name_email = "foo@foo.org",
            expiration_days = 10)

        # key created ?
        self.assertNotEqual(self._repository.get_keys(), {})
        self.assert_(self._repository.is_pubkey_available("foo.org"))

        # sign file
        rand_file = _misc.get_random_file()
        asc_file = rand_file + ".asc"
        self._repository.sign_file("foo.org", rand_file)
        self._repository.verify_file("foo.org", rand_file, asc_file)

        # try to verify against wrong file
        wrong_rand_file = _misc.get_random_file_md5()
        self.assertEqual(
            self._repository.verify_file("foo.org", wrong_rand_file, asc_file),
            False)

        # now craft signature
        with open(asc_file, "w") as asc_f:
            asc_f.write("0")
            asc_f.flush()

        self.assertEqual(
            self._repository.verify_file("foo.org", rand_file, asc_file),
            False)

        os.remove(asc_file)

if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
