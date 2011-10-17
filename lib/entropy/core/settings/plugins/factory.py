# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy SystemSettings Plugins factory module}.

"""
from entropy.core import EntropyPluginFactory
from entropy.core.settings.plugins.skel import SystemSettingsPlugin
import entropy.core.settings.plugins.interfaces as plugs

FACTORY = EntropyPluginFactory(SystemSettingsPlugin, plugs)

# get available plugins from Factory
# returns a dict, see EntropyPluginFactory documentation
get_available_plugins = FACTORY.get_available_plugins
