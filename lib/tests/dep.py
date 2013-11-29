# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
from entropy.const import const_convert_to_rawstring, const_convert_to_unicode
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
        self.assertTrue(et.is_valid_package_tag(valid))
        for invalid in invalids:
            self.assertTrue(not et.is_valid_package_tag(invalid))

    def test_isjustname(self):
        self.assertTrue(not et.isjustname("app-foo/foo-1.2.3"))
        self.assertTrue(et.isjustname("app-foo/foo"))

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
        package_category = "app-foo"
        package_name = "foo"
        package_version = "1.2.3"
        package_tag = "abc"
        package_sha1 = "c85320d9ddb90c13f4a215f1f0a87b531ab33310"
        package_rev = 123

        result = "app-foo:foo-1.2.3#abc.c85320d9ddb90c13f4a215f1f0a87b531ab33310~123.tbz2"
        self.assertEqual(et.create_package_filename(
                package_category, package_name, package_version,
                package_tag, revision = package_rev,
                sha1 = package_sha1), result)

        # verify the inverse function
        cat, name, ver, tag, sha1, rev = et.exploit_package_filename(
            result)
        self.assertEqual(cat, package_category)
        self.assertEqual(name, package_name)
        self.assertEqual(ver, package_version)
        self.assertEqual(tag, package_tag)
        self.assertEqual(sha1, package_sha1)
        self.assertEqual(rev, package_rev)

    def test_create_package_atom_string(self):
        category = "app-foo"
        name = "foo"
        version = "1.2.3"
        package_tag = "abc"
        result = 'app-foo/foo-1.2.3#abc'
        self.assertEqual(et.create_package_atom_string(category, name, version,
            package_tag), result)

    def __open_test_db(self):
        from entropy.client.interfaces import Client
        client = Client(installed_repo = -1, indexing = False, xcache = False,
            repo_validation = False)
        db = client.open_temp_repository(name = "parser_test",
            temp_file = ":memory:")
        client.destroy()
        client.shutdown()
        return db

    def __open_spm(self):
        from entropy.client.interfaces import Client
        client = Client()
        spm = client.Spm()
        client.destroy()
        client.shutdown()
        return spm

    def test_parser(self):
        pkgs = _misc.get_test_packages_and_atoms()
        test_db = self.__open_test_db()
        spm = self.__open_spm()

        deps = []
        for dep, path in pkgs.items():
            data = spm.extract_package_metadata(path)
            idpackage = test_db.addPackage(data)
            data2 = test_db.getPackageData(idpackage)

            _misc.clean_pkg_metadata(data)
            _misc.clean_pkg_metadata(data2)
            self.assertEqual(data, data2)
            deps.append(dep)
        deps.sort()

        depstrings = [
            ("( %s & %s ) | cacca" % (deps[0], deps[1]), [deps[0], deps[1]]),
            ("%s | ( cacca | cacca ) | cacca" % (deps[0],), [deps[0]]),
            ("( app-foo/foo | %s ) & ( %s & %s ) %s" % (deps[0], deps[1], deps[2], deps[3]), [deps[0], deps[1], deps[2], deps[3]]),
            ("cacca | ( cacca | cacca ) | cacca", []),
        ]

        for depstring, expected_outcome in depstrings:
            parser = et.DependencyStringParser(depstring, [test_db])
            result, outcome = parser.parse()
            self.assertEqual(outcome, expected_outcome)

    def test_parser_selected(self):
        pkgs = _misc.get_test_packages_and_atoms()
        test_db = self.__open_test_db()
        spm = self.__open_spm()

        deps = []
        for dep, path in pkgs.items():
            data = spm.extract_package_metadata(path)
            idpackage = test_db.addPackage(data)
            data2 = test_db.getPackageData(idpackage)

            _misc.clean_pkg_metadata(data)
            _misc.clean_pkg_metadata(data2)
            self.assertEqual(data, data2)
            deps.append(dep)

        deps.sort()
        selected_matches = [(test_db.atomMatch(deps[2])[0],
            test_db.repository_id())]

        depstrings = [
            ("( %s & %s ) | %s" % (deps[0], deps[1], deps[2]), [deps[2]]),
            ("%s | ( cacca | cacca ) | %s" % (deps[0], deps[2],), [deps[2]]),
        ]

        for depstring, expected_outcome in depstrings:
            parser = et.DependencyStringParser(depstring, [test_db],
                selected_matches = selected_matches)
            result, outcome = parser.parse()
            self.assertEqual(outcome, expected_outcome)

    def test_get_entropy_package_sha1(self):
        names = [
            ("app-foo:bar-123.eda9a5004ce8eb127d939de6ec394571a407f863~1.tbz2",
             "eda9a5004ce8eb127d939de6ec394571a407f863"),
            ]

        for name, expected_outcome in names:
            outcome = et.get_entropy_package_sha1(name)
            self.assertEqual(outcome, expected_outcome)

if __name__ == '__main__':
    unittest.main()
    et.kill_threads()
    raise SystemExit(0)
