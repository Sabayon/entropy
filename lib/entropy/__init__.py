# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework interface}.
    This is the Entropy Framework Python package.
    Entropy is a framework for creation of package management applications,
    also featuring a Portage-compatible binary Package Manager built
    on top of it.

    Code can be divided into 3 main chunks: client, server and services.

        - B{entropy.client}: contains the client interface of the
        Gentoo Portage-compatible package manager and a User Generated Content
        client-side framework.
        - B{entropy.server}: contains the server interface of the
        Gentoo Portage-compatibile package manager.
        - B{entropy.services}: contains Remote Services interfaces (through
        a Python-based secure RPC mechanism) like User Generated Content,
        Server-side Repository management and general Repository services.

"""

