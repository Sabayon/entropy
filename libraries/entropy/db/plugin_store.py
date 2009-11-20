# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework repository database plugin store module}.

"""
from entropy.core import EntropyPluginStore
from entropy.db.skel import EntropyRepositoryPlugin

class EntropyRepositoryPluginStore(EntropyPluginStore):

    """
    EntropyRepository plugin interface. This is the EntropyRepository part
    aimed to handle connected plugins.
    """

    _PERMANENT_PLUGINS = {}

    def __init__(self):
        EntropyPluginStore.__init__(self)
        permanent_plugs = EntropyRepositoryPluginStore.get_permanent_plugins()
        for plug in permanent_plugs.values():
            plug.add_plugin_hook(self)

    def add_plugin(self, entropy_repository_plugin):
        """
        Overloaded from EntropyPluginStore, adds support for hooks execution.
        """
        inst = entropy_repository_plugin
        if not isinstance(inst, EntropyRepositoryPlugin):
            raise AttributeError("EntropyRepositoryPluginStore: " + \
                    "expected valid EntropyRepositoryPlugin instance")
        EntropyPluginStore.add_plugin(self, inst.get_id(), inst)
        inst.add_plugin_hook(self)

    def remove_plugin(self, plugin_id):
        """
        Overloaded from EntropyPluginStore, adds support for hooks execution.
        """
        plugins = self.get_plugins()
        plug_inst = plugins.get(plugin_id)
        if plug_inst is not None:
            plug_inst.remove_plugin_hook(self)
        return EntropyPluginStore.remove_plugin(self, plugin_id)

    @staticmethod
    def add_permanent_plugin(entropy_repository_plugin):
        """
        Add EntropyRepository permanent plugin. This plugin object will be
        used across all the instantiated EntropyRepositoryPluginStore classes.
        Each time a new instance is created, add_plugin_hook will be executed
        for all the permanent plugins.

        @param entropy_repository_plugin: EntropyRepositoryPlugin instance
        @type entropy_repository_plugin: EntropyRepositoryPlugin instance
        """
        inst = entropy_repository_plugin
        if not isinstance(inst, EntropyRepositoryPlugin):
            raise AttributeError("EntropyRepositoryPluginStore: " + \
                    "expected valid EntropyRepositoryPlugin instance")
        EntropyRepositoryPluginStore._PERMANENT_PLUGINS[inst.get_id()] = inst

    @staticmethod
    def remove_permanent_plugin(plugin_id):
        """
        Remove EntropyRepository permanent plugin. This plugin object will be
        removed across all the EntropyRepository instances around.
        Please note: due to the fact that there are no destructors around,
        the "remove_plugin_hook" callback won't be executed when calling this
        static method.

        @param plugin_id: EntropyRepositoryPlugin identifier
        @type plugin_id: string
        @raise KeyError: in case of unavailable plugin identifier
        """
        del EntropyRepositoryPluginStore._PERMANENT_PLUGINS[plugin_id]

    @staticmethod
    def get_permanent_plugins():
        """
        Return EntropyRepositoryStore installed permanent plugins.

        @return: copy of internal permanent plugins dict
        @rtype: dict
        """
        return EntropyRepositoryPluginStore._PERMANENT_PLUGINS.copy()

    def get_plugins(self):
        """
        Overloaded from EntropyPluginStore, adds support for permanent plugins.
        """
        plugins = EntropyPluginStore.get_plugins(self)
        plugins.update(EntropyRepositoryPluginStore.get_permanent_plugins())
        return plugins

    def get_plugins_metadata(self):
        """
        Return EntropyRepositoryPluginStore registered plugins metadata.

        @return: plugins metadata
        @rtype: dict
        """
        plugins = self.get_plugins()
        meta = {}
        for plugin_id in plugins:
            meta.update(plugins[plugin_id].get_metadata())
        return meta

    def get_plugin_metadata(self, plugin_id, key):
        """
        Return EntropyRepositoryPlugin metadata value referenced by "key".

        @param plugin_id. EntropyRepositoryPlugin identifier
        @type plugin_id: string
        @param key: EntropyRepositoryPlugin metadatum identifier
        @type key: string
        @return: metadatum value
        @rtype: any Python object
        @raise KeyError: if provided key or plugin_id is not available
        """
        plugins = self.get_plugins()
        return plugins[plugin_id][key]

    def set_plugin_metadata(self, plugin_id, key, value):
        """
        Set EntropyRepositoryPlugin stored metadata.

        @param plugin_id. EntropyRepositoryPlugin identifier
        @type plugin_id: string
        @param key: EntropyRepositoryPlugin metadatum identifier
        @type key: string
        @param value: value to set
        @type value: any valid Python object
        @raise KeyError: if plugin_id is not available
        """
        plugins = self.get_plugins()
        meta = plugins[plugin_id].get_metadata()
        meta[key] = value
