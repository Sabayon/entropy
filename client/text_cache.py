# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

from entropy.client.interfaces import Client
def cache(options):
    rc = 0
    if len(options) < 1:
        return -10

    Equo = Client(noclientdb = True)
    if options[0] == "clean":
        Equo.purge_cache()
    elif options[0] == "generate":
        Equo.generate_cache()
    else:
        rc = -10
    Equo.destroy()

    return rc




