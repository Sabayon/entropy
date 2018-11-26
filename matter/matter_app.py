#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

"""
import sys
import os

from os import path as osp
_base = osp.dirname(osp.dirname(osp.realpath(__file__)))
if os.path.isfile(osp.join(_base, "entropy-in-vcs-checkout")):
    sys.path.insert(0, osp.join(_base, "entropy_path_loader"))
    import entropy_path_loader
    entropy_path_loader.add_import_path("matter")
del osp

from matter.main import main

if __name__ == "__main__":
    sys.argv[0] = "matter"
    raise SystemExit(main())
