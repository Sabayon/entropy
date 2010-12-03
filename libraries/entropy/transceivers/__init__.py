# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy base transceivers module}.

"""
import os
import time
import tempfile

from entropy.tools import print_traceback, get_file_size, \
    convert_seconds_to_fancy_output, bytes_into_human, spliturl
from entropy.const import const_isnumber
from entropy.output import TextInterface, blue, brown, darkgreen, red
from entropy.i18n import _
from entropy.misc import Lifo
from entropy.transceivers.exceptions import TransceiverError, \
    UriHandlerNotFound, TransceiverConnectionError
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler


class EntropyTransceiver(TextInterface):

    """
    Base class for Entropy transceivers. This provides a common API across
    all the available URI handlers.

    How to use this class:
    Let's consider that we have a valid EntropyUriHandler for ftp:// protocol
    already installed via "add_uri_handler".

    >> txc = EntropyTransceiver("ftp://myuser:mypwd@myhost")
    >> txc.set_speed_limit(150) # set speed limit to 150kb/sec
    >> handler = txc.swallow()
    >> handler.download("ftp://myuser:mypwd@myhost/myfile.txt", "/tmp")
        # download 
    """

    _URI_HANDLERS = []

    @staticmethod
    def add_uri_handler(entropy_uri_handler_class):
        """
        Add custom URI handler to EntropyTransceiver class.

        @param entropy_uri_handler_class: EntropyUriHandler based class
        @type entropy_uri_handler_class; EntropyUriHandler instance
        """
        if not issubclass(entropy_uri_handler_class, EntropyUriHandler):
            raise AttributeError("EntropyUriHandler based class expected")
        EntropyTransceiver._URI_HANDLERS.append(entropy_uri_handler_class)

    @staticmethod
    def remove_uri_handler(entropy_uri_handler_class):
        """
        Remove custom URI handler to EntropyTransceiver class.

        @param entropy_uri_handler_class: EntropyUriHandler based instance
        @type entropy_uri_handler_class; EntropyUriHandler instance
        @raise ValueError: if provided EntropyUriHandler is not in storage.
        """
        if not issubclass(entropy_uri_handler_class, EntropyUriHandler):
            raise AttributeError("EntropyUriHandler based class expected")
        EntropyTransceiver._URI_HANDLERS.remove(entropy_uri_handler_class)

    @staticmethod
    def get_uri_handlers():
        """
        Return a copy of the internal list of URI handler instances.

        @return: URI handlers instances list
        @rtype: list
        """
        return EntropyTransceiver._URI_HANDLERS[:]

    @staticmethod
    def get_uri_name(uri):
        """
        Given an URI, extract and return the URI name (hostname).

        @param uri: URI to handle
        @type uri: string
        @return: URI name
        @rtype: string
        @raise UriHandlerNotFound: if no URI handlers can deal with given URI
            string
        """
        handlers = EntropyTransceiver.get_uri_handlers()
        for handler in handlers:
            if handler.approve_uri(uri):
                return handler.get_uri_name(uri)

        raise UriHandlerNotFound(
            "no URI handler available for %s" % (uri,))

    @staticmethod
    def hide_sensible_data(uri):
        """
        Given an URI, hide sensible data from string and return it back.

        @param uri: URI to handle
        @type uri: string
        @return: URI cleaned
        @rtype: string
        @raise UriHandlerNotFound: if no URI handlers can deal with given URI
            string
        """
        handlers = EntropyTransceiver.get_uri_handlers()
        for handler in handlers:
            if handler.approve_uri(uri):
                return handler.hide_sensible_data(uri)

        raise UriHandlerNotFound(
            "no URI handler available for %s" % (uri,))

    def __init__(self, uri):
        """
        EntropyTransceiver constructor, just pass the friggin URI(tm).

        @param uri: URI to handle
        @type uri: string
        """
        self._uri = uri
        self._speed_limit = 0
        self._verbose = False
        self._timeout = None
        self._silent = None
        self._output_interface = None
        self.__with_stack = Lifo()

    def __enter__(self):
        """
        Support for "with" statement, this method will execute swallow() and
        return a valid EntropyUriHandler instance.
        """
        handler = self.swallow()
        self.__with_stack.push(handler)
        return handler

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Support for "with" statement, this method will automagically close the
        previously created EntropyUriHandler instance connection.
        """
        handler = self.__with_stack.pop() # if this fails, it's not a good sign
        handler.close()

    def set_output_interface(self, output_interface):
        """
        Provide alternative Entropy output interface (must be based on
        entropy.output.TextInterface)

        @param output_interface: new entropy.output.TextInterface instance to
            use
        @type output_interface: entropy.output.TextInterface based instance
        @raise AttributeError: if argument passed is not correct
        """
        if not isinstance(output_interface, TextInterface):
            raise AttributeError(
                "expected a valid TextInterface based instance")
        self._output_interface = output_interface

    def set_speed_limit(self, speed_limit):
        """
        Set download/upload speed limit in kb/sec form.
        Zero value will be considered as "disable speed limiter".

        @param speed_limit: speed limit in kb/sec form.
        @type speed_limit: int
        @raise AttributeError: if speed_limit is not an integer
        """
        if not const_isnumber(speed_limit):
            raise AttributeError("expected a valid number")
        self._speed_limit = speed_limit

    def set_timeout(self, timeout):
        """
        Set transceiver tx/rx timeout value in seconds.

        @param timeout: timeout in seconds
        @type timeout: int
        """
        if not const_isnumber(timeout):
            raise AttributeError("not a number")
        self._timeout = timeout

    def set_silent(self, silent):
        """
        Disable transceivers verbosity.

        @param verbosity: verbosity value
        @type verbosity: bool
        """
        self._silent = silent

    def set_verbosity(self, verbosity):
        """
        Set transceiver verbosity.

        @param verbosity: verbosity value
        @type verbosity: bool
        """
        if not isinstance(verbosity, bool):
            raise AttributeError("expected a valid bool")
        self._verbose = verbosity

    def swallow(self):
        """
        Given the URI at the constructor, this method returns the first valid
        URI handler instance found that can be used to do required action.

        @raise entropy.exceptions.UriHandlerNotFound: when URI handler for given
            URI is not available.
        """
        handlers = EntropyTransceiver.get_uri_handlers()
        for handler in handlers:
            if handler.approve_uri(self._uri):
                handler_instance = handler(self._uri)
                if self._output_interface is not None:
                    handler_instance.set_output_interface(
                        self._output_interface)
                if const_isnumber(self._speed_limit):
                    handler_instance.set_speed_limit(self._speed_limit)
                handler_instance.set_verbosity(self._verbose)
                handler_instance.set_silent(self._silent)
                if const_isnumber(self._timeout):
                    handler_instance.set_timeout(self._timeout)
                return handler_instance

        raise UriHandlerNotFound(
            "no URI handler available for %s" % (self._uri,))

###
# Automatically add installed plugins
###
from .uri_handlers.plugins import factory
available_plugins = factory.get_available_plugins()
for plug_id in available_plugins:
    EntropyTransceiver.add_uri_handler(available_plugins[plug_id])
