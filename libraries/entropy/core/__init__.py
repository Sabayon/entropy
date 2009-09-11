# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework core module}.

    This module contains base classes used by entropy.client,
    entropy.server and entropy.services.

    "Singleton" is a class that is inherited from singleton objects.

"""
import sys
import os
import inspect
from entropy.const import etpConst

class Singleton(object):

    """
    If your class wants to become a sexy Singleton,
    subclass this and replace __init__ with init_singleton
    """

    __is_destroyed = False
    __is_singleton = True
    def __new__(cls, *args, **kwds):
        instance = cls.__dict__.get("__it__")
        if instance is not None:
            if not instance.is_destroyed():
                return instance
        cls.__it__ = instance = object.__new__(cls)
        instance.init_singleton(*args, **kwds)
        return instance

    def is_destroyed(self):
        """
        In our world, Singleton instances may be destroyed,
        this is done by setting a private bool var __is_destroyed

        @rtype: bool
        @return: instance status, if destroyed or not
        """
        return self.__is_destroyed

    def is_singleton(self):
        """
        Return if the instance is a singleton

        @rtype: bool
        @return: class singleton property, if singleton or not
        """
        return self.__is_singleton


class EntropyPluginFactory:

    """
    Generic Entropy Components Plugin Factory (loader).
    """

    _PLUGIN_SUFFIX = "_plugin"
    _PYTHON_EXTENSION = ".py"

    def __init__(self, base_plugin_class, plugin_package_module,
        default_plugin_name = None, fallback_plugin_name = None):
        """
        Entropy Generic Plugin Factory constructor.
        MANDATORY: every plugin module/package(name) must end with _plugin
        suffix.

        Base plugin classes must have the following class attributes set:

            - BASE_PLUGIN_API_VERSION: integer describing API revision in use
              in class

        Subclasses of Base plugin class must have the following class
        attributes set:

            - PLUGIN_API_VERSION: integer describing the currently implemented
              plugin API revision, must match with BASE_PLUGIN_API_VERSION
              above otherwise plugin won't be loaded and a warning will be
              printed.

        Moreover, plugin classes must be "Python new-style classes", otherwise
        parser won't be able to determine if classes have subclasses and thus
        pick the proper object (one with no subclasses!!).
        See: http://www.python.org/doc/newstyle -- in other words, you have
        to inherit the built-in "object" class (yeah, it's called object).
        So, even if using normal classes could work, if you start doing nasty
        things (nested inherittance of plugin classes), behaviour cannot
        be guaranteed.
        If it's not clear, let me repeat once again, valid plugin classes
        must not have subclasses around! Think about it, it's an obvious thing.

        If plugin class features a "PLUGIN_DISABLED" class attribute with
        a boolean value of True, such plugin will be ignored.

        @param base_plugin_class: Base EntropyPlugin-based class that valid
            plugin classes must inherit from.
        @type base_plugin_class: class
        @param plugin_package_module: every plugin repository must work as
            Python package, the value of this argument must be a valid
            Python package module that can be scanned looking for valid
            Entropy Plugin classes.
        @type plugin_package_module: Python module
        @keyword default_plugin_name: identifier of the default plugin to load
        @type default_plugin_name: string
        @keyword fallback_plugin_name: identifier of the fallback plugin to load
            if default is not available
        @type fallback_plugin_name: string
        @raise AttributeError: when passed plugin_package_module is not a
            valid Python package module
        """
        self.__modfile = plugin_package_module.__file__
        self.__base_class = base_plugin_class
        self.__plugin_package_module = plugin_package_module
        self.__default_plugin_name = default_plugin_name
        self.__fallback_plugin_name = fallback_plugin_name
        self.__cache = None


    def get_available_plugins(self):
        """
        Return currently available EntropyPlugin plugin classes.
        Note: Entropy plugins can either be Python packages or modules and
        their name MUST end with PluginFactory._PLUGIN_SUFFIX ("_plugin").

        @return: dictionary composed by Entropy plugin id as key and Entropy
            Python module as value
        @rtype: dict
        """
        if self.__cache is not None:
            return self.__cache.copy()

        available = {}
        base_api = self.__base_class.BASE_PLUGIN_API_VERSION

        pkg_modname = self.__plugin_package_module.__name__
        for modname in os.listdir(os.path.dirname(self.__modfile)):

            if modname.startswith("__"):
                continue # python stuff
            if not (modname.endswith(EntropyPluginFactory._PYTHON_EXTENSION) \
                or "." not in modname):
                continue # not something we want to load

            if modname.endswith(EntropyPluginFactory._PYTHON_EXTENSION):
                modname = modname[:-len(EntropyPluginFactory._PYTHON_EXTENSION)]

            if not modname.endswith(EntropyPluginFactory._PLUGIN_SUFFIX):
                continue

            # remove suffix
            modname_clean = modname[:-len(EntropyPluginFactory._PLUGIN_SUFFIX)]

            modpath = "%s.%s" % (pkg_modname, modname,)

            try:
                __import__(modpath)
            except ImportError, err:
                sys.stderr.write("!!! Entropy Plugin warning, cannot " \
                    "load module: %s | %s !!!\n" % (modpath, err,))
                continue

            for obj in sys.modules[modpath].__dict__.values():

                if not inspect.isclass(obj):
                    continue

                if not issubclass(obj, self.__base_class):
                    continue

                if hasattr(obj, '__subclasses__'):
                    # new style class
                    if obj.__subclasses__(): # only lower classes taken
                        continue
                else:
                    sys.stderr.write("!!! Entropy Plugin warning: " \
                        "%s is not a new style class !!!\n" % (obj,))

                if obj is self.__base_class:
                    # in this case, obj is our base class,
                    # so we are very sure that obj is not valid
                    continue

                if not hasattr(obj, "PLUGIN_API_VERSION"):
                    sys.stderr.write("!!! Entropy Plugin warning: " \
                        "no PLUGIN_API_VERSION in %s !!!\n" % (obj,))
                    continue

                if obj.PLUGIN_API_VERSION != base_api:
                    sys.stderr.write("!!! Entropy Plugin warning: " \
                        "PLUGIN_API_VERSION mismatch in %s !!!\n" % (obj,))
                    continue

                if hasattr(obj, 'PLUGIN_DISABLED'):
                    if obj.PLUGIN_DISABLED:
                        # this plugin has been disabled
                        continue

                available[modname_clean] = obj

        self.__cache = available.copy()
        return available

    def get_default_plugin(self):
        """
        Return currently configured Entropy Plugin class.

        @return: Entropy plugin class
        @rtype: entropy.core.EntropyPlugin
        @raise KeyError: if default plugin is not set or not found
        """
        available = self.get_available_plugins()
        plugin = self.__default_plugin_name
        fallback = self.__fallback_plugin_name
        klass = available.get(plugin)

        if klass is None:
            import warnings
            warnings.warn("%s: %s" % (
                "selected Plugin not available, using fallback", plugin,))
            klass = available.get(fallback)

        if klass is None:
            raise KeyError

        return klass
