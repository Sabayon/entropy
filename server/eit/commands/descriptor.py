# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.
    Eit Command descriptor class.

"""

class EitCommandDescriptor(object):
    """
    EitCommand descriptor object used for
    help information purposes.
    """

    EIT_COMMANDS = []
    EIT_COMMANDS_MAP = {}

    @staticmethod
    def register(descriptor):
        """
        Register an EitCommandDescriptor object
        """
        EitCommandDescriptor.EIT_COMMANDS.append(descriptor)
        EitCommandDescriptor.EIT_COMMANDS_MAP[descriptor.get_name()] = \
            descriptor

    @staticmethod
    def obtain():
        """
        Get the list of registered EitCommandDescriptor object
        """
        return EitCommandDescriptor.EIT_COMMANDS[:]

    @staticmethod
    def obtain_descriptor(name):
        """
        Get a registered EitCommandDescritor object
        through its name.

        @param name: name of the EitCommandDescriptor
        @type name: string
        @raise KeyError: if name isn't bound to any
        EitCommandDescriptor object.
        """
        return EitCommandDescriptor.EIT_COMMANDS_MAP[name]

    def __init__(self, klass, name, description):
        self._klass = klass
        self._name = name
        self._description = description

    def get_class(self):
        """
        Get EitCommand class bound to this command
        """
        return self._klass

    def get_name(self):
        """
        Get EitCommand name
        """
        return self._name

    def get_description(self):
        """
        Get EitCommand description
        """
        return self._description
