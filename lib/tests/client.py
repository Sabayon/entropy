# -*- coding: utf-8 -*-
import sys
import unittest
import os
import shutil
import signal
import time

from os import path as osp
_base = osp.dirname(osp.dirname(osp.dirname(osp.realpath(__file__))))
sys.path.insert(0, osp.join(_base, "entropy_path_loader"))
import entropy_path_loader
del osp

from entropy.client.interfaces import Client
from entropy.client.interfaces.db import InstalledPackagesRepository
from entropy.client.interfaces.package.actions._triggers import Trigger
from entropy.cache import EntropyCacher
from entropy.const import etpConst, const_mkdtemp
from entropy.output import set_mute
from entropy.core.settings.base import SystemSettings
from entropy.db import EntropyRepository
from entropy.exceptions import RepositoryError, EntropyPackageException
import entropy.tools
import tests._misc as _misc

class EntropyClientTest(unittest.TestCase):

    def setUp(self):
        self.mem_repoid = "mem_repo"
        self.mem_repo_desc = "This is a testing repository"
        self.Client = Client(installed_repo = -1, indexing = False,
            xcache = False, repo_validation = False)
        self.Client._real_installed_repository = self.Client.open_temp_repository(
            name = InstalledPackagesRepository.NAME, temp_file = ":memory:")
        # as per GenericRepository specifications, enable generic handlePackage
        self.Client._installed_repository.override_handlePackage = True
        self.Spm = self.Client.Spm()
        self._settings = SystemSettings()
        self.test_pkgs = [_misc.get_entrofoo_test_package()]

    def tearDown(self):
        """
        tearDown is run after each test
        """
        # calling destroy() and shutdown()
        # need to call destroy() directly to remove all the SystemSettings
        # plugins because shutdown() doesn't, since it's meant to be called
        # right before terminating the process
        self.Client.destroy()
        self.Client.shutdown()

    def test_singleton(self):
        myclient = Client(installed_repo = -1)
        self.assertTrue(myclient is self.Client)
        myclient.shutdown()
        self.assertTrue(myclient.is_destroyed())
        self.assertTrue(self.Client.is_destroyed())
        myclient2 = Client(installed_repo = -1, indexing = False,
            xcache = False, repo_validation = False)
        self.assertTrue(myclient is not myclient2)
        myclient2.shutdown()
        self.assertTrue(myclient2.is_destroyed())

    def test_syssetting_backup(self):
        key1 = 'foo_foo_foo2'
        key2 = 'asdasdadsadas'
        val1 = set([1, 2, 3])
        val2 = None
        foo_data = {
            key1: val1,
            key2: val2,
        }
        self._settings.update(foo_data)
        self._settings.set_persistent_setting(foo_data)
        self._settings.clear()
        self.assertEqual(True, key1 in self._settings)
        self.assertEqual(True, key2 in self._settings)
        self.assertEqual(val1, self._settings.get(key1))
        self.assertEqual(val2, self._settings.get(key2))

        # now remove
        self._settings.unset_persistent_setting(key1)
        self._settings.clear()
        self.assertEqual(False, key1 in self._settings)
        self.assertEqual(True, key2 in self._settings)

        self._settings.unset_persistent_setting(key2)
        self._settings.clear()
        self.assertEqual(False, key1 in self._settings)
        self.assertEqual(False, key2 in self._settings)

    def test_entropy_cacher(self):
        self.Client._cacher.start()
        self.assertTrue(self.Client._cacher.is_started())
        self.Client._cacher.stop()
        self.assertTrue(not self.Client._cacher.is_started())

    def test_cacher_lock_usage(self):
        cacher = self.Client._cacher
        tmp_dir = const_mkdtemp()
        cacher.start()
        try:
            with cacher:
                self.assertTrue(cacher._EntropyCacher__enter_context_lock._is_owned())
                cacher.discard()
                # even if cacher is paused, this must be saved
                cacher.save("foo", "bar", cache_dir = tmp_dir)
                self.assertEqual(cacher.pop("foo", cache_dir = tmp_dir), "bar")
        finally:
            cacher.stop()
            shutil.rmtree(tmp_dir, True)

    def test_cacher_general_usage(self):
        cacher = self.Client._cacher
        tmp_dir = const_mkdtemp()
        cacher.start()
        st_val = EntropyCacher.STASHING_CACHE
        try:
            EntropyCacher.STASHING_CACHE = True
            with cacher:
                self.assertTrue(
                    cacher._EntropyCacher__enter_context_lock._is_owned())
                cacher.discard()
                cacher.push("bar", "foo", cache_dir = tmp_dir)
                self.assertTrue(cacher._EntropyCacher__cache_buffer)
                self.assertTrue(cacher._EntropyCacher__stashing_cache)
            cacher.sync()
            self.assertEqual(cacher.pop("bar", cache_dir = tmp_dir), "foo")
        finally:
            EntropyCacher.STASHING_CACHE = st_val
            cacher.stop()
            shutil.rmtree(tmp_dir, True)

    def test_cacher_push_pop_sync(self):
        cacher = self.Client._cacher
        tmp_dir = const_mkdtemp()
        cacher.stop()
        try:
            cacher.push("bar", "foo", async_mode = False, cache_dir = tmp_dir)
            # must return None
            cacher.sync()
            self.assertEqual(cacher.pop("bar", cache_dir = tmp_dir), None)
        finally:
            shutil.rmtree(tmp_dir, True)

    def test_clear_cache(self):
        current_dir = self.Client._cacher.current_directory()
        test_file = os.path.join(current_dir, "asdasd")
        with open(test_file, "w") as f:
            f.flush()
        self.Client.clear_cache()
        self.assertEqual(os.listdir(current_dir), [])

    def test_contentsafety(self):
        dbconn = self.Client._init_generic_temp_repository(
            self.mem_repoid, self.mem_repo_desc, temp_file = ":memory:")
        test_pkg = _misc.get_test_entropy_package5()
        tmp_dir = const_mkdtemp()
        rc = entropy.tools.uncompress_tarball(test_pkg, extract_path = tmp_dir)
        self.assertEqual(rc, 0)

        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = dbconn.addPackage(data)
        db_data = dbconn.getPackageData(idpackage)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(db_data)
        self.assertEqual(data, db_data)

        cs_data = dbconn.retrieveContentSafety(idpackage)
        for path, cs_info in cs_data.items():
            real_path = os.path.join(tmp_dir, path.lstrip("/"))
            self.assertEqual(os.path.getmtime(real_path), cs_info['mtime'])
        shutil.rmtree(tmp_dir)

    def test_memory_repository(self):
        dbconn = self.Client._init_generic_temp_repository(
            self.mem_repoid, self.mem_repo_desc, temp_file = ":memory:")
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = dbconn.addPackage(data)
        db_data = dbconn.getPackageData(idpackage)

        _misc.clean_pkg_metadata(data)
        _misc.clean_pkg_metadata(db_data)
        self.assertEqual(data, db_data)

        self.Client.remove_repository(self.mem_repoid)
        self.assertNotEqual(
            self.Client._memory_db_instances.get(self.mem_repoid), dbconn)
        def test_load():
            set_mute(True)
            self.Client.open_repository(self.mem_repoid)
            set_mute(False)
        self.assertRaises(RepositoryError, test_load)

    def test_package_repository(self):
        test_pkg = _misc.get_test_entropy_package()
        # this might fail on 32bit arches
        atoms_contained = []
        try:
            atoms_contained = self.Client.add_package_repository(test_pkg)
        except EntropyPackageException as err:
            if etpConst['currentarch'] == "amd64":
                raise
            self.assertEqual(str(err), "invalid architecture")
        else:
            self.assertNotEqual([], atoms_contained)
            for idpackage, repoid in atoms_contained:
                dbconn = self.Client.open_repository(repoid)
                self.assertNotEqual(None, dbconn.getPackageData(idpackage))
                self.assertNotEqual(None, dbconn.retrieveAtom(idpackage))

    def test_package_installation_new_api(self):
        for pkg_path, pkg_atom in self.test_pkgs:
            self._do_pkg_test_new_api(pkg_path, pkg_atom)

    def test_shell_trigger(self):
        dbconn = self.Client._init_generic_temp_repository(
            self.mem_repoid, self.mem_repo_desc, temp_file = ":memory:")
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = dbconn.addPackage(data)
        pkgdata = dbconn.getTriggerData(idpackage)
        trigger = None
        try:
            pkgdata['affected_directories'] = set()
            pkgdata['affected_infofiles'] = set()
            pkgdata['trigger'] = """\
#!%s
echo >/dev/null
exit 42
""" % (etpConst['trigger_sh_interpreter'],)
            trigger = Trigger(
                self.Client, "install", 'postinstall', pkgdata, pkgdata)
            trigger.prepare()
            exit_st = trigger._do_trigger_call_ext_generic()
            trigger.kill()
        finally:
            if trigger is not None:
                trigger.kill()

        self.assertEqual(exit_st, 42)

    def test_python_trigger(self):
        dbconn = self.Client._init_generic_temp_repository(
            self.mem_repoid, self.mem_repo_desc, temp_file = ":memory:")
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = dbconn.addPackage(data)
        pkgdata = dbconn.getTriggerData(idpackage)
        trigger = None
        try:
            pkgdata['affected_directories'] = set()
            pkgdata['affected_infofiles'] = set()
            pkgdata['trigger'] = """\
import os
os.listdir(".")
my_ext_status = 42
"""
            trigger = Trigger(
                self.Client, "install", 'postinstall', pkgdata, pkgdata)
            trigger.prepare()
            exit_st = trigger._do_trigger_call_ext_generic()
        finally:
            if trigger is not None:
                trigger.kill()
        self.assertEqual(exit_st, 42)

    def test_python_trigger2(self):
        dbconn = self.Client._init_generic_temp_repository(
            self.mem_repoid, self.mem_repo_desc, temp_file = ":memory:")
        test_pkg = _misc.get_test_package()
        data = self.Spm.extract_package_metadata(test_pkg)
        idpackage = dbconn.addPackage(data)
        pkgdata = dbconn.getTriggerData(idpackage)
        trigger = None
        try:
            pkgdata['affected_directories'] = set()
            pkgdata['affected_infofiles'] = set()
            pkgdata['trigger'] = """\
import os
import subprocess
from entropy.const import etpConst

def configure_correct_gcc():
    gcc_target = "4.5"
    uname_arch = os.uname()[4]
    if uname_arch:
        return 42
    return 24

if stage == "postinstall":
    my_ext_status = configure_correct_gcc()
else:
    my_ext_status = 0
"""
            trigger = Trigger(
                self.Client, "install", 'postinstall', pkgdata, pkgdata)
            trigger.prepare()
            exit_st = trigger._do_trigger_call_ext_generic()
        finally:
            if trigger is not None:
                trigger.kill()

        self.assertEqual(exit_st, 42)

    def _do_pkg_test_new_api(self, pkg_path, pkg_atom):

        # this test might be considered controversial, for now, let's keep it
        # here, we use equo stuff to make sure it keeps working
        from _entropy.solo.commands.pkg import SoloPkg

        # we need to tweak the default unpack dir to make pkg install available
        # for uids != 0
        temp_unpack = const_mkdtemp()
        old_unpackdir = etpConst['entropyunpackdir']
        etpConst['entropyunpackdir'] = temp_unpack

        fake_root = const_mkdtemp()
        pkg_dir = const_mkdtemp()
        inst_dir = const_mkdtemp()

        s_pkg = SoloPkg(["inflate", pkg_path, "--savedir", pkg_dir])
        func, func_args = s_pkg.parse()
        # do not call func directly because the real method is
        # wrapper around a lock call
        rc = s_pkg._inflate(self.Client)
        self.assertTrue(rc == 0)
        self.assertTrue(os.listdir(pkg_dir))

        final_pkg_dir = os.path.join(pkg_dir, os.path.dirname(pkg_atom))

        etp_pkg = os.path.join(final_pkg_dir, os.listdir(final_pkg_dir)[0])
        self.assertTrue(os.path.isfile(etp_pkg))

        matches = []
        try:
            matches = self.Client.add_package_repository(etp_pkg)
        except EntropyPackageException as err:
            if etpConst['currentarch'] == "amd64":
                raise
            self.assertEqual(str(err), "invalid architecture")
        else:
            self.assertNotEqual(matches, [])

            action_factory = self.Client.PackageActionFactory()
            for match in matches:
                my_p = action_factory.get(
                    action_factory.INSTALL_ACTION,
                    match)
                my_p.setup()

                # unit testing metadata setting, of course, undocumented
                my_p.metadata()['unittest_root'] = fake_root

                rc = my_p.start()
                self.assertTrue(rc == 0)
                my_p.finalize()

        # remove pkg
        idpackages = self.Client.installed_repository().listAllPackageIds()
        for idpackage in idpackages:
            my_p = action_factory.get(
                action_factory.REMOVE_ACTION,
                (idpackage, self.Client.installed_repository().name))
            rc = my_p.start()
            self.assertTrue(rc == 0)
            my_p.finalize()

        # done installing
        shutil.rmtree(pkg_dir, True)
        shutil.rmtree(temp_unpack, True)
        shutil.rmtree(fake_root, True)

        # restore orig const value
        etpConst['entropyunpackdir'] = old_unpackdir


if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
