# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager Plugins factory module}.

"""
from entropy.core import EntropyPluginFactory
from entropy.core.settings.base import SystemSettings
from entropy.spm.plugins.skel import SpmPlugin
import entropy.spm.plugins.interfaces as plugs

_settings = SystemSettings()
_USER_PLUG = _settings['system'].get('spm_backend')

FACTORY = EntropyPluginFactory(SpmPlugin, plugs,
    default_plugin_name = _USER_PLUG)

get_available_plugins = FACTORY.get_available_plugins

def get_default_class():
    """
    Return default Source Package Manager plugin class.

    @return: default Source Package Manager plugin class
    @raise SystemError: if no default plugin class has been specified.
        This usually means a programming error.
    """
    fallback_used = False
    myplugs = get_available_plugins()
    if _USER_PLUG is not None:
        user_plugin = myplugs.get(_USER_PLUG)
        if user_plugin is not None:
            return user_plugin
        fallback_used = True

    for plug_id in sorted(myplugs):
        plug_class = myplugs[plug_id]
        if plug_class.IS_DEFAULT:
            if fallback_used:
                import warnings
                warnings.warn("%s: %s" % (
                    "User configured Source Package Manager Plugin not available, "
                    "using fallback", plug_id,))
            return plug_class

    raise SystemError("no SPM default plugin configured")

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
