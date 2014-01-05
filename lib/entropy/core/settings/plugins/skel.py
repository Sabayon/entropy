# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework SystemSettings stub classes module}.

    SystemSettingsPlugin is the base class for building valid SystemSettings
    plugin modules (see entropy.client.interfaces.client or
    entropy.server.interfaces for working examples).

"""

class SystemSettingsPlugin(object):

    BASE_PLUGIN_API_VERSION = 3

    """

    This is a plugin base class for all SystemSettings plugins.
    It allows to add extra parsers (though metadata) to
    SystemSettings.
    Just inherit from this class and call add_parser to add
    your custom parsers.
    SystemSettings will call the parse method, as explained below.

    Sample code:

    >>> # load SystemSettings
    >>> from entropy.core.settings.base import SystemSettings
    >>> from entropy.core.settings.plugins.skel import SystemSettingsPlugin
    >>> system_settings = SystemSettings()
    >>> class MyPlugin(SystemSettingsPlugin):
    >>>      pass
    >>> my_plugin = MyPlugin('mystuff', None)
    >>> def myparsing_function():
    >>>     return {'abc': 1 }
    >>> my_plugin.add_parser('parser_no_1', myparsing_function)
    >>> system_settings.add_plugin(my_plugin)
    >>> print(system_settings['mystuff']['parser_no_1'])
    {'abc': 1 }
    >>> # let's remove it
    >>> system_settings.remove_plugin('mystuff') # through its plugin_id
    >>> print(system_settings.get('mystuff'))
    None

    """

    def __init__(self, plugin_id, helper_interface):
        """
        SystemSettingsPlugin constructor.

        @param plugin_id: plugin identifier, must be unique
        @type plugin_id: string
        @param helper_interface: any Python object that could
            be of help to your parsers
        @type handler_instance: Python object
        @rtype: None
        @return: None
        """
        self.__parsers = []
        self.__plugin_id = plugin_id
        self._helper = helper_interface
        parser_postfix = "_parser"
        for method in sorted(dir(self)):
            if method == "add_parser":
                continue
            elif method.startswith("_"):
                # private method
                continue
            elif method.endswith(parser_postfix) and (method != parser_postfix):
                parser_id = method[:len(parser_postfix)*-1]
                self.__parsers.append((parser_id, getattr(self, method),))

    def get_id(self):
        """
        Returns the unique plugin id passed at construction time.

        @return: plugin identifier
        @rtype: string
        """
        return self.__plugin_id

    def get_updatable_configuration_files(self, repository_id):
        """
        Return a list (set) of updatable configuration files for this plugin.
        For "updatable" it is meant, configuration files that expose
        package matches (not just keys) at the beginning of new lines.
        This makes possible to implement automatic configuration files updates
        upon package name renames.
        Please override this method if interested in exposing conf files.

        @param repository_id: repository identifier, if needed to return
            a list of specific configuration files
        @type repository_id: string or None
        @return: list (set) of package files paths (must check for path avail)
        @rtype: set
        """
        return None

    def add_parser(self, parser_id, parser_callable):
        """
        You must call this method in order to add your custom
        parsers to the plugin.
        Please note, if your parser method ends with "_parser"
        it will be automatically added this way:

        method: foo_parser
            parser_id => foo
        method: another_fabulous_parser
            parser_id => another_fabulous

        @param parser_id: parser identifier, must be unique
        @type parser_id: string
        @param parser_callable: any callable function which has
            the following signature: callable(system_settings_instance)
            can return True to stop further parsers calls
        @type parser_callable: callable
        @return: None
        @rtype: None
        """
        self.__parsers.append((parser_id, parser_callable,))

    def parse(self, system_settings_instance):
        """
        This method is called by SystemSettings instance
        when building its settings metadata.

        Returned data from parser will be put into the SystemSettings
        dict using plugin_id and parser_id keys.
        If returned data is None, SystemSettings dict won't be changed.

        @param system_settings_instance: SystemSettings instance
        @type system_settings_instance: SystemSettings instance
        @return: the parsed metadata
        @rtype: dict
        """
        metadata = {}

        for parser_id, parser in self.__parsers:
            data = parser(system_settings_instance)
            if data is None:
                continue
            metadata[parser_id] = data

        return metadata

    def post_setup(self, system_settings_instance):
        """
        This method is called by SystemSettings instance
        after having built all the SystemSettings metadata.
        You can reimplement this and hook your refinement code
        into this method.

        @param system_settings_instance: SystemSettings instance
        @type system_settings_instance: SystemSettings instance
        @return: None
        @rtype: None
        """
        pass
