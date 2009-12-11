# -*- coding: utf-8 -*-
import os
from entropy.exceptions import FileNotFound

def get_test_generic_package(test_pkg):
    path1 = os.path.join(os.getcwd(), "packages", test_pkg)
    path2 = os.path.join(os.getcwd(), "..", "packages", test_pkg)
    if os.path.lexists(path1):
        return path1
    elif os.path.lexists(path2):
        return path2
    raise FileNotFound("cannot find test package %s" % (test_pkg,))

def get_test_package():
    test_pkg = "zlib-1.2.3-r1.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_package2():
    test_pkg = "aspell-es-0.50.2.tbz2"
    return get_test_generic_package(test_pkg)

def get_footar_package():
    test_pkg = "footar.tar.bz2"
    return get_test_generic_package(test_pkg)

def get_test_package3():
    test_pkg = "apache-tools-2.2.11.tbz2"
    return get_test_generic_package(test_pkg)

def get_entrofoo_test_package():
    test_pkg = "entrofoo-1.tbz2"
    return get_test_generic_package(test_pkg), "app-misc/entrofoo"

def get_entrofoo_test_spm_portage_dir():
    test_pkg = "portage/entrofoo-2"
    return get_test_generic_package(test_pkg)

def get_test_entropy_package():
    test_pkg = "sys-libs:zlib-1.2.3-r1~1.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_entropy_package2():
    test_pkg = "xfce-extra:xfce4-verve-0.3.6~4.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_entropy_package3():
    test_pkg = "virtual:poppler-qt3-0.10.6~1.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_entropy_package4():
    test_pkg = "x11-base:xorg-server-1.5.3-r6~1.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_entropy_package_provide():
    test_pkg = "mail-mta:ssmtp-2.62-r7~0.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_xpak_empty_package():
    test_pkg = "aspell-es-0.50.2.tbz2"
    return get_test_generic_package(test_pkg)

def get_png():
    test_pkg = "sabayon.png"
    return get_test_generic_package(test_pkg)

def get_dl_so_amd():
    test_pkg = "libdl-2.10.1.so"
    return get_test_generic_package(test_pkg)

def get_dl_so_amd_2():
    test_pkg = "libkdb5.so.4.0"
    return get_test_generic_package(test_pkg)

def get_test_package_name():
    return "zlib"

def get_test_package_name2():
    return "aspell-es"

def get_test_package_name3():
    return "apache-tools"

def get_test_package_atom():
    return "sys-libs/zlib-1.2.3-r1"

def get_test_package_atom2():
    return "app-dicts/aspell-es-0.50.2"

def get_test_package_atom3():
    return "app-admin/apache-tools-2.2.11"

def get_random_file():
    return get_test_generic_package("random_file")

def get_random_file_md5():
    return get_test_generic_package("random_file.md5")