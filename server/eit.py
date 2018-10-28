#!/usr/bin/python
import os
import sys

os.environ['ETP_GETTEXT_DOMAIN'] = "entropy-server"

from os import path as osp
_base = osp.dirname(osp.dirname(osp.realpath(__file__)))
if os.path.isfile(osp.join(_base, "entropy-in-vcs-checkout")):
    sys.path.insert(0, osp.join(_base, "entropy_path_loader"))
else:
    sys.path.insert(0, "/usr/lib/entropy/entropy_path_loader")
del osp
import entropy_path_loader

from eit.main import main
sys.argv[0] = "eit"
main()
