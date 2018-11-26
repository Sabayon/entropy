# -*- coding: utf-8 -*-
"""

    @author: Slawomir Nizio <slawomir.nizio@sabayon.org>
    @contact: lxnay@sabayon.org, slawomir.nizio@sabayon.org
    @copyright: Slawomir Nizio
    @license: GPL-2

    B{Python module path setter}.

    This module sets paths to other modules from sources checkout.
    It must not be imported in case of installed application, system wide or
    otherwise.

"""
import sys
from os import path as osp

base_dir = osp.dirname(osp.dirname(osp.realpath(__file__)))
in_checkout = osp.isfile(osp.join(base_dir, "entropy-in-vcs-checkout"))


def add_import_path(mod):
    if not in_checkout:
        raise RuntimeError(
            "entropy_path_loader used when not in checkout")
    lib = osp.join(base_dir, mod)
    sys.path.insert(0, lib)


mods = (
    "client",
    "server",
    "lib",
    "magneto/src",
    "entropy_path_loader/compat"
)

for mod in mods:
    add_import_path(mod)
