import os
from entropy.exceptions import FileNotFound

def get_test_package():
    test_pkg = "zlib-1.2.3-r1.tbz2"
    path1 = os.path.join(os.getcwd(), test_pkg)
    path2 = os.path.join(os.getcwd(), "..", test_pkg)
    if os.path.isfile(path1):
        return path1
    elif os.path.isfile(path2):
        return path2
    raise FileNotFound("cannot find test package %s" % (test_pkg,))