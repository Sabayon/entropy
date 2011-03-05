# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
from entropy.output import blue, brown, darkgreen
from entropy.i18n import _

def cache(options):

    if not options:
        return -10
    cmd = options.pop(0)

    rc = 0

    from entropy.client.interfaces import Client
    entropy_client = None
    try:
        entropy_client = Client(installed_repo = False)
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
        if entropy_client is not None:
            entropy_client.shutdown()

    return rc




