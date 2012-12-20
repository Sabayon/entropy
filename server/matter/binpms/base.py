# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

    Basic implementation of a Binary Package Manager interface
    to Matter.

"""
import os

# default mandatory features
os.environ['ACCEPT_PROPERTIES'] = "* -interactive"
os.environ['FEATURES'] = "split-log"
os.environ['CMAKE_NO_COLOR'] = "yes"


class BaseBinaryResourceLock(object):
    """
    This class exposes a Lock-like interface for acquiring PMS
    resources.
    """

    class NotAcquired(Exception):
        """ Raised when Lock cannot be acquired """

    def __init__(self, blocking):
        """
        BaseBinaryResourceLock constructor.

        @param blocking: acquire lock in blocking mode?
        @type blocking: bool
        """
        self._blocking = blocking

    def acquire(self):
        """
        Acquire the Resource Lock.
        """

    def release(self):
        """
        Release the Resource Lock.
        """

    def __enter__(self):
        """
        Acquire lock. Not thread-safe.
        """

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Release lock. Not thread-safe.
        """


class BaseBinaryPMS(object):
    """
    Base class for implementing a Binary Package Manager
    System for Matter.
    """

    available_pms = []
    DEFAULT = True
    NAME = "base"


    @staticmethod
    def register(klass):
        """
        Register a Binary PMS object so that it can be loaded
        by Matter at initialization time.
        """
        BaseBinaryPMS.available_pms.append(klass)

    class BasePMSError(Exception):
        """ Base exception for all the BaseBinaryPMS exceptions. """

    class BinaryPMSLoadError(BasePMSError):
        """ Raised when the BinaryPMS system cannot be initalized. """

    class SpecParserError(BasePMSError):
        """ Raised when an invalid SpecParser object is found. """

    class SystemValidationError(BasePMSError):
        """ Raised when the System is not able to accept a Matter run. """

    class RepositoryCommitError(BasePMSError):
        """ Raised when a repository commit fails. """

    class RepositoryPushError(BasePMSError):
        """ Raised when a repository push fails. """

    def __init__(self, nsargs):
        """
        Constructor.

        @param nsargs: ArgumentParser's parsed arguments
        @type nsargs: ArgumentParser
        """
        self._nsargs = nsargs
        from _emerge.actions import load_emerge_config
        self._cfg_loader = load_emerge_config

    def get_resource_lock(self, blocking):
        """
        Return a Binary Package Manager resource lock
        object that Matter can use to acquire exclusive
        access to the PMS.
        The base implementation does not do anything.

        @param blocking: if True, the lock is acquired in
            blocking mode, otherise not. If lock cannot be
            acquired, a BaseBinaryResourceLock.NotAcquired
            exception is raised.
        @type blocking: bool
        @return: a BaseBinaryResourceLock based instance.
        @rtype: BaseBinaryResourceLock
        """
        return BaseBinaryResourceLock(blocking)

    def shutdown(self):
        """
        Shutdown the Binary Package Manager System.
        """

    def validate_spec(self, spec):
        """
        Validate Matter SpecParser's .spec file metadata.

        @param spec: a SpecParser object.
        @type spec: SpecParser
        @raises SpecParserError: if the SpecParser object contains
            invalid metadata.
        """

    def check_preserved_libraries(self, emerge_config=None):
        """
        Ask Portage whether there are preserved libraries on the system.
        This usually indicates that Entropy packages should not be really
        committed.

        @keyword emerge_config: tuple returned by load_emerge_config(),
            -> (emerge_settings, emerge_trees, mtimedb)
        @type emerge_config: tuple
        @return: True, if preserved libraries are found
        @rtype: bool
        """
        if emerge_config is None:
            emerge_config = self.load_emerge_config()
        emerge_settings, emerge_trees, _mtimedb = emerge_config
        vardb = emerge_trees[emerge_settings["ROOT"]]["vartree"].dbapi
        vardb._plib_registry.load()
        return vardb._plib_registry.hasEntries()

    def load_emerge_config(self):
        """
        Call _emerge.load_emerge_config() to load Portage configuration
        and return it.
        """
        return self._cfg_loader()

    def validate_system(self):
        """
        Validate System status. Check whether system is ready
        to accept a Matter execution.
        If System is not ready, a SystemValidationError exception
        is raised.
        """
        if not self._nsargs.disable_preserved_libs:
            if self.check_preserved_libraries():
                raise BaseBinaryPMS.SystemValidationError(
                    "preserved libraries are found on "
                    "the system, aborting.")

    def commit(self, repository, packages):
        """
        Commit packages to the BinaryPMS repository.
        """

    def push(self, repository):
        """
        Push all the packages built by PackageBuilder to the
        given repository.
        """


BaseBinaryPMS.register(BaseBinaryPMS)
