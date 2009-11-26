# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Transceivers class prototypes module}.

"""
from entropy.const import const_isnumber
from entropy.output import TextInterface

class EntropyUriHandler(object, TextInterface):

    BASE_PLUGIN_API_VERSION = 0

    """
    Base class for EntropyTransceiver URI handler interfaces. This provides
    a common API for implementing custom URI handlers.

    To add your URI handler to EntropyTransceiver, do the following:
    >>> EntropyTransceiver.add_uri_handler(my_entropy_transceiver_based_instance)
    "add_uri_handler" is a EntropyTransceiver static method.
    """
    def __init__(self, uri):
        """
        EntropyUriHandler constructor.
        When constructor is called, instance should perform a connection and
        permissions check and raise entropy.exceptions.ConnectionError in case
        of issues.

        @param uri: URI to handle
        @type uri: string
        """
        object.__init__(self)
        self._uri = uri
        self._speed_limit = 0
        self._verbose = False
        self._silent = False
        self._timeout = None

    def __enter__(self):
        """
        Support for "with" statement, this will trigger UriHandler connection
        setup.
        """
        raise NotImplementedError()

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Support for "with" statement, this will trigger UriHandler connection
        hang up.
        """
        raise NotImplementedError()

    @staticmethod
    def approve_uri(uri):
        """
        Approve given URI by returning True or False depending if this
        class is able to handle it.

        @param uri: URI to handle
        @type uri: string
        @return: True, if URI can be handled by this class
        @rtype: bool
        """
        raise NotImplementedError()

    @staticmethod
    def get_uri_name(uri):
        """
        Given a valid URI (meaning that implementation can handle the provided
        URI), it extracts and returns the URI name (hostname).

        @param uri: URI to handle
        @type uri: string
        @return: URI name
        @rtype: string
        """
        raise NotImplementedError()

    @staticmethod
    def hide_sensible_data(uri):
        """
        Given an URI, hide sensible data from string and return it back.

        @param uri: URI to handle
        @type uri: string
        @return: URI cleaned
        @rtype: string
        """
        raise NotImplementedError()

    def get_uri(self):
        """
        Return copy of previously stored URI.

        @return: stored URI
        @rtype: string
        """
        return self._uri[:]

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
        self.updateProgress = output_interface.updateProgress
        self.askQuestion = output_interface.askQuestion

    def set_speed_limit(self, speed_limit):
        """
        Set download/upload speed limit in kb/sec form.

        @param speed_limit: speed limit in kb/sec form.
        @type speed_limit: int
        """
        if not const_isnumber(speed_limit):
            raise AttributeError("not a number")
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
        Disable transceiver verbosity.

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
        self._verbose = verbosity

    def download(self, remote_path, save_path):
        """
        Download URI and save it to save_path.

        @param remote_path: remote path to handle
        @type remote_path: string
        @param save_path: complete path where to store file from uri.
            If directory doesn't exist, it will be created with default
            Entropy permissions.
        @type save_path: string
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def upload(self, load_path, remote_path):
        """
        Upload URI from load_path location to uri.

        @param load_path: remote path to handle
        @type load_path: string
        @param remote_path: remote path to handle ("directory"/"file name" !)
        @type remote_path: string
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def rename(self, remote_path_old, remote_path_new):
        """
        Rename URI old to URI new.

        @param remote_path_old: remote path to handle
        @type remote_path_old: string
        @param remote_path_new: remote path to create
        @type remote_path_new: string
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def delete(self, remote_path):
        """
        Remove the remote path (must be a file).

        @param remote_path_old: remote path to remove (only file allowed)
        @type remote_path_old: string
        @return: True, if operation went successful
        @rtype: bool
        @return: execution status, True if done
        @rtype: bool
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def get_md5(self, remote_path):
        """
        Return MD5 checksum of file at URI.

        @param remote_path: remote path to handle
        @type remote_path: string
        @return: MD5 checksum in hexdigest form
        @rtype: string or None (if not supported)
        """
        raise NotImplementedError()

    def list_content(self, remote_path):
        """
        List content of directory referenced at URI.

        @param remote_path: remote path to handle
        @type remote_path: string
        @return: content
        @rtype: list
        @raise ValueError: if remote_path does not exist
        """
        raise NotImplementedError()

    def list_content_metadata(self, remote_path):
        """
        List content of directory referenced at URI with metadata in this form:
        [(name, size, owner, group, permissions<drwxr-xr-x>,), ...]
        permissions, owner, group, size, name.

        @param remote_path: remote path to handle
        @type remote_path: string
        @return: content
        @rtype: list
        @raise ValueError: if remote_path does not exist
        """
        raise NotImplementedError()

    def is_path_available(self, remote_path):
        """
        Given a remote path (which can point to dir or file), determine whether
        it's available or not.

        @param remote_path: URI to handle
        @type remote_path: string
        @return: availability
        @rtype: bool
        """
        raise NotImplementedError()

    def is_dir(self, remote_path):
        """
        Given a remote path (which can point to dir or file), determine whether
        it's a directory.

        @param remote_path: URI to handle
        @type remote_path: string
        @return: True, if remote_path is a directory
        @rtype: bool
        """
        raise NotImplementedError()

    def is_file(self, remote_path):
        """
        Given a remote path (which can point to dir or file), determine whether
        it's a file.

        @param remote_path: URI to handle
        @type remote_path: string
        @return: True, if remote_path is a file
        @rtype: bool
        """
        raise NotImplementedError()

    def makedirs(self, remote_path):
        """
        Given a remote path, recursively create all the missing directories.

        @param remote_path: URI to handle
        @type remote_path: string
        """
        raise NotImplementedError()

    def keep_alive(self):
        """
        Send a keep-alive ping to handler.
        @raise ConnectionError: if problems happen
        """
        raise NotImplementedError()

    def close(self):
        """
        Called when requesting to close connection completely.
        """
        raise NotImplementedError()
