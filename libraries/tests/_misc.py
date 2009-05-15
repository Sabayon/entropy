# -*- coding: utf-8 -*-
import os
from entropy.exceptions import FileNotFound

def get_test_generic_package(test_pkg):
    path1 = os.path.join(os.getcwd(), test_pkg)
    path2 = os.path.join(os.getcwd(), "..", test_pkg)
    if os.path.isfile(path1):
        return path1
    elif os.path.isfile(path2):
        return path2
    raise FileNotFound("cannot find test package %s" % (test_pkg,))

def get_test_package():
    test_pkg = "zlib-1.2.3-r1.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_package2():
    test_pkg = "aspell-es-0.50.2.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_package3():
    test_pkg = "apache-tools-2.2.11.tbz2"
    return get_test_generic_package(test_pkg)

def get_test_entropy_package():
    test_pkg = "sys-libs:zlib-1.2.3-r1~1.tbz2"
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