# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Interfaces}.

"""

from entropy.server.interfaces.main import Server, \
    ServerSystemSettingsPlugin, RepositoryConfigParser
from entropy.server.interfaces.mirrors import Server as MirrorsServer
