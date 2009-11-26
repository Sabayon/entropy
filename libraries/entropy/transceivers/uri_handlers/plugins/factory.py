# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{EntropyTransceiver URI handlers plugins factory module}.

"""
from entropy.core import EntropyPluginFactory
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler
from . import interfaces as plugs

# get available plugins from Factory
# returns a dict, see EntropyPluginFactory documentation
FACTORY = EntropyPluginFactory(EntropyUriHandler, plugs)
get_available_plugins = FACTORY.get_available_plugins