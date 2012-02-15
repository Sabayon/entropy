# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
from entropy.output import blue, brown, darkgreen, print_error
from entropy.i18n import _

import entropy.tools

def cache(options):

    if not options:
        return -10
    cmd = options.pop(0)

    rc = 0

    from entropy.client.interfaces import Client
    entropy_client = None
    acquired = False
    try:
        entropy_client = Client(installed_repo = False)
        acquired = entropy.tools.acquire_entropy_locks(entropy_client)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1

        if cmd == "clean":
            entropy_client.output(
                blue(_("Cleaning Entropy cache, please wait ...")),
                level = "info",
                header = brown(" @@ "),
                back = True
            )
            entropy_client.clear_cache()
            entropy_client.output(
                darkgreen(_("Entropy cache cleaned.")),
                level = "info",
                header = brown(" @@ ")
            )
        else:
            rc = -10
    finally:
        if acquired and (entropy_client is not None):
            entropy.tools.release_entropy_locks(entropy_client)
        if entropy_client is not None:
            entropy_client.shutdown()

    return rc

