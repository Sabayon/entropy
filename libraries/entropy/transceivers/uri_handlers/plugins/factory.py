# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{EntropyTransceiver URI handlers plugins factory module}.

"""
from entropy.core import EntropyPluginFactory
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler
try:
    from . import interfaces as plugs
except ImportError:
    from .. import interfaces as plugs

# get available plugins from Factory
# returns a dict, see EntropyPluginFactory documentation
FACTORY = EntropyPluginFactory(EntropyUriHandler, plugs)
get_available_plugins = FACTORY.get_available_plugins