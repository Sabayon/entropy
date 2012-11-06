# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.
    Solo Command descriptor class.

"""

class SoloCommandDescriptor(object):
    """
    SoloCommand descriptor object used for
    help information purposes.
    """

    SOLO_COMMANDS = []
    SOLO_COMMANDS_MAP = {}

    @staticmethod
    def register(descriptor):
        """
        Register an SoloCommandDescriptor object
        """
        SoloCommandDescriptor.SOLO_COMMANDS.append(descriptor)
        SoloCommandDescriptor.SOLO_COMMANDS_MAP[descriptor.get_name()] = \
            descriptor

    @staticmethod
    def obtain():
        """
        Get the list of registered SoloCommandDescriptor object
        """
        return SoloCommandDescriptor.SOLO_COMMANDS[:]

    @staticmethod
    def obtain_descriptor(name):
        """
        Get a registered SoloCommandDescritor object
        through its name.

        @param name: name of the SoloCommandDescriptor
        @type name: string
        @raise KeyError: if name isn't bound to any
        SoloCommandDescriptor object.
        """
        return SoloCommandDescriptor.SOLO_COMMANDS_MAP[name]

    def __init__(self, klass, name, description):
        self._klass = klass
        self._name = name
        self._description = description

    def get_class(self):
        """
        Get SoloCommand class bound to this command
        """
        return self._klass

    def get_name(self):
        """
        Get SoloCommand name
        """
        return self._name

    def get_description(self):
        """
        Get SoloCommand description
        """
        return self._description
