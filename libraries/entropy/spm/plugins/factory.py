# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager Plugins factory module}.

"""
import os
import sys
from entropy.const import etpConst
from entropy.core import SystemSettings
from entropy.i18n import _
from entropy.spm.plugins.skel import SpmPlugin
PLUGIN_SUFFIX = "_plugin"
_AVAILABLE_CACHE = None

def get_available_plugins():
    """
    Return currently available Source Package Manager plugin classes.
    Note: SPM plugins can either be Python packages or modules and
    their name MUST end with "_plugin".

    @return: dictionary composed by SPM plugin id as key and SPM Python
        module as value
    @rtype: dict
    """
    global _AVAILABLE_CACHE

    if _AVAILABLE_CACHE is not None:
        return _AVAILABLE_CACHE.copy()

    available = {}
    import imp
    import entropy.spm.plugins.interfaces as plugs
    modpath = plugs.__file__
    for modname in os.listdir(os.path.dirname(modpath)):

        if modname.startswith("__"):
            continue # python stuff
        if not (modname.endswith(".py") or "." not in modname):
            continue # not something we want to load

        if modname.endswith(".py"):
            modname = modname[:-3]

        if not modname.endswith(PLUGIN_SUFFIX):
            continue

        # remove suffix
        modname_clean = modname[:-len(PLUGIN_SUFFIX)]

        modpath = "entropy.spm.plugins.interfaces.%s" % (modname,)
        module = __import__(modpath)
        for obj in sys.modules[modpath].__dict__.values():

            try:
                if not issubclass(obj, SpmPlugin):
                    continue
                if obj.__subclasses__(): # only lower classes taken
                    continue
            except (TypeError, AttributeError,):
                continue

            available[modname_clean] = obj

    _AVAILABLE_CACHE = available.copy()
    return available


def get_default_class():
    """
    Return currently configured Entropy Source Package Manager plugin class.

    @return: Entropy Source Package Manager plugin class
    @rtype: entropy.spm.plugins.skel.SpmPlugin
    """
    settings = SystemSettings()
    backend = settings['system'].get('spm_backend', etpConst['spm']['backend'])
    available = get_available_plugins()
    klass = available.get(backend)
    if klass is None:
        import warnings
        warnings.warn("%s: %s" % (
            _("selected SPM backend not available"), backend,))
        klass = available.get(etpConst['spm']['backend'])
    return klass


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
