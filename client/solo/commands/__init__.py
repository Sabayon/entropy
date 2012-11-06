# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import sys

_cur_file = sys.modules[__name__].__file__
_cur_dir = os.path.dirname(_cur_file)
_excluded_mods = ["descriptor"]
for py_file in os.listdir(_cur_dir):
    if not py_file.endswith(".py"):
        continue
    if py_file.startswith("_"):
        continue
    # strip .py
    _mod = "solo.commands." + py_file[:-3]
    if _mod in _excluded_mods:
        continue
    try:
        __import__(_mod)
    except ValueError:
        # garbage
        continue
