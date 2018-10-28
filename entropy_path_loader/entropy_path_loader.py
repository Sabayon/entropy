# -*- coding: utf-8 -*-
"""

    @author: Slawomir Nizio <slawomir.nizio@sabayon.org>
    @contact: lxnay@sabayon.org, slawomir.nizio@sabayon.org
    @copyright: Slawomir Nizio
    @license: GPL-2

    B{Python module path setter}.

    This is a module that sets paths to other modules, which can be installed
    on system or taken from sources checkout.

"""
import sys
from os import path as osp

base_dir = osp.dirname(osp.dirname(osp.realpath(__file__)))
in_checkout = osp.isfile(osp.join(base_dir, "entropy-in-vcs-checkout"))

# Ugly, can go away if paths are in sys.path.
mods_outside_entropy_dir = set([
    "rigo",
    "matter"
])


def add_import_path(mod):
    if in_checkout:
        base = base_dir
    elif mod in mods_outside_entropy_dir:
        base = "/usr/lib"
    else:
        base = "/usr/lib/entropy"

    lib = osp.join(base, mod)
    sys.path.insert(0, lib)


mods = (
    "client",
    "server",
    "lib"
)

for mod in mods:
    add_import_path(mod)
