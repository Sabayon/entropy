# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager Plugins factory module}.

"""
from entropy.const import etpConst
from entropy.core import EntropyPluginFactory
from entropy.core.settings.base import SystemSettings
from entropy.i18n import _
from entropy.spm.plugins.skel import SpmPlugin
import entropy.spm.plugins.interfaces as plugs

settings = SystemSettings()
default_plugin = settings['system'].get('spm_backend',
    etpConst['spm']['backend'])

FACTORY = EntropyPluginFactory(SpmPlugin, plugs,
    default_plugin_name = default_plugin,
    fallback_plugin_name = etpConst['spm']['backend'])

get_available_plugins = FACTORY.get_available_plugins
get_default_class = FACTORY.get_default_plugin

def get_default_instance(output_interface):
    """
    Return the currently configured Entropy SPM interface instance.

    @param output_interface: Entropy Output Interface instance
    @type output_interface: entropy.output.TextInterface based instance
    @return: currently selected SPM interface
    @rtype: entropy.spm.plugins.skel.SpmPlugin based instance
    """
    spm_class = get_default_class()
    return spm_class(output_interface)
