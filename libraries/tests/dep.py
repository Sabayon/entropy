# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
from entropy.const import const_convert_to_rawstring, const_convert_to_unicode
from entropy.client.interfaces import Client
from entropy.output import print_generic
import tests._misc as _misc
import tempfile
import subprocess
import shutil
import stat
import entropy.dep as et

class DepTest(unittest.TestCase):

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()
        self.test_pkg = _misc.get_test_entropy_package()
        self.test_pkg2 = _misc.get_test_entropy_package2()
        self.test_pkg3 = _misc.get_test_entropy_package3()
        self.test_pkgs = [self.test_pkg, self.test_pkg2, self.test_pkg3]

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()

    def test_valid_package_tag(self):
        valid = "ciao"
        invalids = ["òpl", "hello,hello", "#hello"]
        self.assert_(et.is_valid_package_tag(valid))
        for invalid in invalids:
            self.assert_(not et.is_valid_package_tag(invalid))

    def test_isjustname(self):
        self.assert_(not et.isjustname("app-foo/foo-1.2.3"))
        self.assert_(et.isjustname("app-foo/foo"))

    def test_catpkgsplit(self):
        data = {
            'app-foo/foo-1.2.3': ("app-foo", "foo", "1.2.3", "r0"),
            'www-apps/389-foo-1.2.3': ("www-apps", "389-foo", "1.2.3", "r0"),
        }
        for atom, split_data in data.items():
            pkgsplit = et.catpkgsplit(atom)
            self.assertEqual(split_data, pkgsplit)

    def test_dep_getkey(self):
        pkg = "app-foo/foo-1.2.3"
        key = "app-foo/foo"
        self.assertEqual(key, et.dep_getkey(pkg))

    def test_dep_getcpv(self):
        pkg = ">=app-foo/foo-1.2.3"
        cpv = "app-foo/foo-1.2.3"
        self.assertEqual(cpv, et.dep_getcpv(pkg))

    def test_dep_getslot(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4"
        slot = "2.3.4"
        self.assertEqual(slot, et.dep_getslot(pkg))

    def test_dep_getusedeps(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4[ciao,come,va]"
        usedeps = ("ciao", "come", "va")
        self.assertEqual(usedeps, et.dep_getusedeps(pkg))

    def test_remove_usedeps(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4[ciao,come,va]"
        result = ">=app-foo/foo-1.2.3:2.3.4"
        self.assertEqual(result, et.remove_usedeps(pkg))

    def test_remove_slot(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4"
        result = ">=app-foo/foo-1.2.3"
        self.assertEqual(result, et.remove_slot(pkg))

    def test_remove_revision(self):
        pkg = "app-foo/foo-1.2.3-r1"
        result = "app-foo/foo-1.2.3"
        self.assertEqual(result, et.remove_revision(pkg))

    def test_remove_tag(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo"
        result = "app-foo/foo-1.2.3-r1"
        self.assertEqual(result, et.remove_tag(pkg))

    def test_remove_entropy_revision(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo~1"
        result = "app-foo/foo-1.2.3-r1#2.2.2-foo"
        self.assertEqual(result, et.remove_entropy_revision(pkg))

    def test_dep_get_entropy_revision(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo~1"
        result = 1
        self.assertEqual(result, et.dep_get_entropy_revision(pkg))

    def test_dep_get_spm_revision(self):
        pkg = "app-foo/foo-1.2.3-r1"
        result = "r1"
        self.assertEqual(result, et.dep_get_spm_revision(pkg))

    def test_dep_get_match_in_repos(self):
        pkg = "app-foo/foo-1.2.3-r1@foorepo"
        result = ("app-foo/foo-1.2.3-r1", ["foorepo"])
        self.assertEqual(result, et.dep_get_match_in_repos(pkg))

    def test_dep_gettag(self):
        pkg = "app-foo/foo-1.2.3-r1#2.2.2-foo~1"
        result = "2.2.2-foo"
        self.assertEqual(result, et.dep_gettag(pkg))

    def test_remove_package_operators(self):
        pkg = ">=app-foo/foo-1.2.3:2.3.4~1"
        result = "app-foo/foo-1.2.3:2.3.4~1"
        self.assertEqual(result, et.remove_package_operators(pkg))

    def test_compare_versions(self):
        ver_a = ("1.0.0", "1.0.0", 0,)
        ver_b = ("1.0.1", "1.0.0", 0.10000000000000001,)
        ver_c = ("1.0.0", "1.0.1", -0.10000000000000001,)

        self.assertEqual(et.compare_versions(ver_a[0], ver_a[1]), ver_a[2])
        self.assertEqual(et.compare_versions(ver_b[0], ver_b[1]), ver_b[2])
        self.assertEqual(et.compare_versions(ver_c[0], ver_c[1]), ver_c[2])

    def test_get_newer_version(self):
        vers = ["1.0", "3.4", "0.5", "999", "9999", "10.0"]
        out_vers = ['9999', '999', '10.0', '3.4', '1.0', '0.5']
        self.assertEqual(et.get_newer_version(vers), out_vers)

    def test_get_entropy_newer_version(self):
        vers = [("1.0", "2222", 1,), ("3.4", "2222", 0,), ("1.0", "2223", 1,),
            ("1.0", "2223", 3,)]
        out_vers = [('1.0', '2223', 3), ('1.0', '2223', 1),
            ('3.4', '2222', 0), ('1.0', '2222', 1)]
        self.assertEqual(et.get_entropy_newer_version(vers), out_vers)

    def test_create_package_filename(self):
        category = "app-foo"
        name = "foo"
        version = "1.2.3"
        package_tag = "abc"
        result = 'app-foo:foo-1.2.3#abc.tbz2'
        self.assertEqual(et.create_package_filename(category, name, version,
            package_tag), result)

    def test_create_package_atom_string(self):
        category = "app-foo"
        name = "foo"
        version = "1.2.3"
        package_tag = "abc"
        result = 'app-foo/foo-1.2.3#abc'
        self.assertEqual(et.create_package_atom_string(category, name, version,
            package_tag), result)

if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
    et.kill_threads()
    raise SystemExit(0)
