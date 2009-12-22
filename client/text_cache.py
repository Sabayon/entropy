# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

def cache(options):

    if not options:
        return -10
    cmd = options.pop(0)

    rc = 0

    from entropy.client.interfaces import Client
    entropy_client = Client(noclientdb = True)
    try:
        if cmd == "clean":
            entropy_client.purge_cache()
        elif cmd == "generate":
            entropy_client.generate_cache()
        else:
            rc = -10
    finally:
        entropy_client.destroy()

    return rc




