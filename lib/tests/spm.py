# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '.')
sys.path.insert(0, '../')
import unittest
import entropy.tools as et
from entropy.client.interfaces import Client
import tests._misc as _misc
import tempfile
import shutil

from entropy.spm.plugins.interfaces.portage_plugin import \
    PortageEntropyDepTranslator

class SpmTest(unittest.TestCase):

    def setUp(self):
        self.Client = Client(installed_repo = -1, indexing = False,
            xcache = False, repo_validation = False)
        self.test_pkg = _misc.get_test_entropy_package()
        self.test_pkg2 = _misc.get_test_entropy_package2()
        self.test_pkg3 = _misc.get_test_entropy_package3()
        self.test_pkgs = [self.test_pkg, self.test_pkg2, self.test_pkg3]

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

    def test_portage_translator(self):
        deps = {
           """|| ( app-emulation/virtualbox
                 >=app-emulation/virtualbox-bin-2.2.0
           )""": \
"( app-emulation/virtualbox | >=app-emulation/virtualbox-bin-2.2.0 )",

           """|| ( ( gnome-extra/zenity ) ( kde-base/kdialog ) )
""": \
"( ( gnome-extra/zenity ) | ( kde-base/kdialog ) )",

           """|| ( <media-libs/xine-lib-1.2
                   ( >=media-libs/xine-lib-1.2 virtual/ffmpeg ) )
           """: \
"( <media-libs/xine-lib-1.2 | ( >=media-libs/xine-lib-1.2 & virtual/ffmpeg ) )",
        }
        for dep, expected in deps.items():
            tr = PortageEntropyDepTranslator(dep)
            self.assertEqual(expected, tr.translate())

    def test_init(self):
        spm = self.Client.Spm()
        spm2 = self.Client.Spm()
        self.assertTrue(spm is spm2)
        spm_class = self.Client.Spm_class()
        spm_class2 = self.Client.Spm_class()
        self.assertTrue(spm_class is spm_class2)

    def test_basic_methods(self):
        spm = self.Client.Spm()
        spm_class = self.Client.Spm_class()

        path = spm.get_user_installed_packages_file()
        self.assertTrue(path)

        groups = spm_class.get_package_groups()
        self.assertTrue(isinstance(groups, dict))

        keys = spm.package_metadata_keys()
        self.assertTrue(isinstance(keys, list))

        cache_dir = spm.get_cache_directory()
        self.assertTrue(cache_dir)

        sys_pkgs = spm.get_system_packages()
        self.assertTrue(sys_pkgs)
        self.assertTrue(isinstance(sys_pkgs, list))

        path1 = spm.get_merge_protected_paths_mask()
        path2 = spm.get_merge_protected_paths()
        self.assertTrue(isinstance(path1, list))
        self.assertTrue(isinstance(path2, list))

        pkg = spm.convert_from_entropy_package_name("app-foo/foo")
        self.assertTrue(pkg)

    def test_portage_xpak(self):

        spm_class = self.Client.Spm_class()
        if spm_class.PLUGIN_NAME != "portage":
            return

        sums = {}
        paths = []

        from entropy.spm.plugins.interfaces.portage_plugin import xpak
        from entropy.spm.plugins.interfaces.portage_plugin import xpaktools
        temp_unpack = tempfile.mkdtemp()
        temp_unpack2 = tempfile.mkdtemp()
        test_pkg = os.path.join(temp_unpack2, "test.pkg")
        dbdir = _misc.get_entrofoo_test_spm_portage_dir()

        for path in os.listdir(dbdir):
            xpath = os.path.join(dbdir, path)
            paths.append(xpath)
            sums[path] = et.md5sum(xpath)

        et.compress_files(test_pkg, paths)
        comp_file = xpak.tbz2(test_pkg)
        result = comp_file.recompose(dbdir)

        shutil.rmtree(temp_unpack)
        os.mkdir(temp_unpack)

        # now extract xpak
        new_sums = {}
        xpaktools.extract_xpak(test_pkg, tmpdir = temp_unpack)
        for path in os.listdir(temp_unpack):
            xpath = os.path.join(temp_unpack, path)
            new_sums[path] = et.md5sum(xpath)

        self.assertEqual(sums, new_sums)

        shutil.rmtree(temp_unpack)
        shutil.rmtree(temp_unpack2)

    def test_extract_xpak(self):

        spm_class = self.Client.Spm_class()
        if spm_class.PLUGIN_NAME != "portage":
            return

        from entropy.spm.plugins.interfaces.portage_plugin import xpaktools
        tmp_path = tempfile.mkdtemp()

        for test_pkg in self.test_pkgs:
            out_path = xpaktools.extract_xpak(test_pkg, tmp_path)
            self.assertNotEqual(out_path, None)
            self.assertTrue(os.listdir(out_path))

        shutil.rmtree(tmp_path, True)


    def test_extract_xpak_only(self):

        spm_class = self.Client.Spm_class()
        if spm_class.PLUGIN_NAME != "portage":
            return

        from entropy.spm.plugins.interfaces.portage_plugin import xpaktools
        pkg_path = _misc.get_test_xpak_empty_package()
        tmp_path = tempfile.mkdtemp()
        out_path = xpaktools.extract_xpak(pkg_path, tmp_path)

        self.assertNotEqual(out_path, None)
        self.assertTrue(os.listdir(out_path))

        shutil.rmtree(tmp_path, True)

    def test_sets_load(self):
        spm = self.Client.Spm()
        sets = spm.get_package_sets(True)
        self.assertNotEqual(sets, None)

    def test_static_sets_load(self):
        spm = self.Client.Spm()
        sets = spm.get_package_sets(False)
        self.assertNotEqual(sets, None)

    def test_dependencies_calculation(self):

        spm_class = self.Client.Spm_class()
        if spm_class.PLUGIN_NAME != "portage":
            return
        spm = self.Client.Spm()

        iuse = "system-sqlite"
        use = "amd64 dbus elibc_glibc kernel_linux multilib " + \
            "startup-notification userland_GNU"
        license = "MPL-1.1 GPL-2"
        depend = """>=mail-client/thunderbird-3.1.1-r1[system-sqlite=]
        x11-libs/libXrender x11-libs/libXt x11-libs/libXmu
        >=sys-libs/zlib-1.1.4 dev-util/pkgconfig x11-libs/libXrender
        x11-libs/libXt x11-libs/libXmu virtual/jpeg dev-libs/expat
        app-arch/zip app-arch/unzip >=x11-libs/gtk+-2.8.6
        >=dev-libs/glib-2.8.2 >=x11-libs/pango-1.10.1 >=dev-libs/libIDL-0.8.0
        >=dev-libs/dbus-glib-0.72 >=x11-libs/startup-notification-0.8
        !<x11-base/xorg-x11-6.7.0-r2 >=x11-libs/cairo-1.6.0 app-arch/unzip
        =sys-devel/automake-1.11* =sys-devel/autoconf-2.1*
        >=sys-devel/libtool-2.2.6b""".replace("\n", " ")
        rdepend = """>=mail-client/thunderbird-3.1.1-r1[system-sqlite=] ||
        ( ( >=app-crypt/gnupg-2.0 || ( app-crypt/pinentry
        app-crypt/pinentry-base ) ) =app-crypt/gnupg-1.4* ) x11-libs/libXrender
        x11-libs/libXt x11-libs/libXmu >=sys-libs/zlib-1.1.4 x11-libs/libXrender
        x11-libs/libXt x11-libs/libXmu virtual/jpeg dev-libs/expat app-arch/zip
        app-arch/unzip >=x11-libs/gtk+-2.8.6 >=dev-libs/glib-2.8.2
        >=x11-libs/pango-1.10.1 >=dev-libs/libIDL-0.8.0
        >=dev-libs/dbus-glib-0.72 >=x11-libs/startup-notification-0.8
        !<x11-base/xorg-x11-6.7.0-r2 >=x11-libs/cairo-1.6.0""".replace("\n", " ")
        pdepend = ""
        provide = ""
        sources = ""
        eapi = "2"

        os.environ['ETP_PORTAGE_CONDITIONAL_DEPS_ENABLE'] = "1"
        try:
            portage_metadata = spm._calculate_dependencies(
                iuse, use, license,
                depend, rdepend, pdepend, provide, sources, eapi)
        finally:
            del os.environ['ETP_PORTAGE_CONDITIONAL_DEPS_ENABLE']

        expected_deps = [
            '>=mail-client/thunderbird-3.1.1-r1[-system-sqlite]',
            '( ( >=app-crypt/gnupg-2.0 & ( app-crypt/pinentry | app-crypt/pinentry-base ) ) | ( app-crypt/pinentry & app-crypt/pinentry-base ) | =app-crypt/gnupg-1.4* )',
            'x11-libs/libXrender',
            'x11-libs/libXt',
            'x11-libs/libXmu',
            '>=sys-libs/zlib-1.1.4',
            'x11-libs/libXrender',
            'x11-libs/libXt',
            'x11-libs/libXmu',
            'virtual/jpeg',
            'dev-libs/expat',
            'app-arch/zip',
            'app-arch/unzip',
            '>=x11-libs/gtk+-2.8.6',
            '>=dev-libs/glib-2.8.2',
            '>=x11-libs/pango-1.10.1',
            '>=dev-libs/libIDL-0.8.0',
            '>=dev-libs/dbus-glib-0.72',
            '>=x11-libs/startup-notification-0.8',
            '!<x11-base/xorg-x11-6.7.0-r2',
            '>=x11-libs/cairo-1.6.0']
        expected_deps.sort()

        resolved_deps = portage_metadata['RDEPEND']
        resolved_deps.sort()

        self.assertEqual(resolved_deps, expected_deps)

    def test_eapi5_portage_slotdeps(self):

        spm_class = self.Client.Spm_class()
        if spm_class.PLUGIN_NAME != "portage":
            return
        spm = self.Client.Spm()

        iuse = "system-sqlite"
        use = "amd64 dbus elibc_glibc kernel_linux multilib " + \
            "startup-notification userland_GNU"
        license = "MPL-1.1 GPL-2"
        depend = """
        >=mail-client/thunderbird-3.1.1-r1:2=[system-sqlite=]
        >=mail-client/thunderbird-3.1.1-r1:2*[system-sqlite=]
        >=mail-client/thunderbird-3.1.1-r1:2*
        >=mail-client/thunderbird-3.1.1-r1:2=
        >=mail-client/thunderbird-3.1.1-r1:=
        >=mail-client/thunderbird-3.1.1-r1:*
        >=mail-client/thunderbird-3.1.1-r1:0/1
        >=mail-client/thunderbird-3.1.1-r1:0/1=
        """.replace("\n", " ")
        rdepend = depend[:]
        pdepend = depend[:]
        provide = ""
        sources = ""
        eapi = "2"

        os.environ['ETP_PORTAGE_CONDITIONAL_DEPS_ENABLE'] = "1"
        try:
            portage_metadata = spm._calculate_dependencies(
                iuse, use, license,
                depend, rdepend, pdepend, provide, sources, eapi)
        finally:
            del os.environ['ETP_PORTAGE_CONDITIONAL_DEPS_ENABLE']

        expected_deps = [
            '>=mail-client/thunderbird-3.1.1-r1:2[-system-sqlite]',
            '>=mail-client/thunderbird-3.1.1-r1:2[-system-sqlite]',
            '>=mail-client/thunderbird-3.1.1-r1:2',
            '>=mail-client/thunderbird-3.1.1-r1:2',
            '>=mail-client/thunderbird-3.1.1-r1',
            '>=mail-client/thunderbird-3.1.1-r1',
            '>=mail-client/thunderbird-3.1.1-r1:0',
            '>=mail-client/thunderbird-3.1.1-r1:0',
            ]
        expected_deps.sort()

        for k in ("RDEPEND", "PDEPEND", "DEPEND"):
            resolved_deps = portage_metadata[k]
            resolved_deps.sort()
            self.assertEqual(resolved_deps, expected_deps)

    def test_portage_or_selector(self):
        spm_class = self.Client.Spm_class()
        if spm_class.PLUGIN_NAME != "portage":
            return
        spm = self.Client.Spm()

        os.environ['ETP_PORTAGE_CONDITIONAL_DEPS_ENABLE'] = "1"
        try:
            or_deps = ['x11-foo/foo', 'x11-bar/bar']
            self.assertEqual(spm._dep_or_select(
                    or_deps, top_level = True),
                             ["( x11-foo/foo | x11-bar/bar )"])
        finally:
            del os.environ['ETP_PORTAGE_CONDITIONAL_DEPS_ENABLE']

if __name__ == '__main__':
    unittest.main()
    raise SystemExit(0)
