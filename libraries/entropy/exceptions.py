# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework exceptions class module}

    This module contains Entropy Framework exceptions classes.

"""
from entropy.const import const_isstring, const_convert_to_unicode

class DumbException(Exception):
    """Dumb exception class"""

class EntropyException(Exception):
    """General superclass for Entropy exceptions"""
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)

    def __unicode__(self):
        if const_isstring(self.value):
            return const_convert_to_unicode(self.value)
        return const_convert_to_unicode(repr(self.value))

    def __str__(self):
        if const_isstring(self.value):
            return self.value
        return repr(self.value)

class SecurityError(EntropyException):
    """ Security related error """

class CorruptionError(EntropyException):
    """Corruption indication"""

class CacheCorruptionError(EntropyException):
    """On-Disk cache Corruption indication"""

class InvalidDependString(EntropyException):
    """An invalid depend string has been encountered"""

class DependenciesNotFound(EntropyException):
    """
    During dependencies calculation, dependencies were not found,
    list (set) of missing dependencies are in the .value attribute
    """

class DependenciesCollision(EntropyException):
    """
    During dependencies calculation, dependencies were pulled in in the same
    "scope" (package key + package slot),
    list of lists (set) of colliding dependencies are in the .value attribute
    """

class DependenciesNotRemovable(EntropyException):
    """
    During dependencies calculation, dependencies got considered
    vital for system health.
    """

class RepositoryError(EntropyException):
    """Cannot open repository database"""

class RepositoryPluginError(EntropyException):
    """Error during EntropyRepositoryPlugin hook execution"""

class InterruptError(EntropyException):
    """Raised to interrupt a thread or process"""

class SystemDatabaseError(EntropyException):
    """Cannot open system database"""

class SPMError(EntropyException):
    """Source Package Manager generic errors"""

class OnlineMirrorError(EntropyException):
    """Mirror issue"""

class QueueError(EntropyException):
    """Action queue issue"""

class InvalidAtom(EntropyException):
    """Atom not properly formatted"""

class InvalidPackageSet(EntropyException):
    """Package set does not exist"""

class FileNotFound(EntropyException):
    """A file was not found when it was expected to exist"""

class DirectoryNotFound(EntropyException):
    """A directory was not found when it was expected to exist"""

class OperationNotPermitted(EntropyException):
    """An operation was not permitted operating system"""

class PermissionDenied(EntropyException):
    """Permission denied"""
    from errno import EACCES as errno

class LibraryNotFound(EntropyException):
    """A required library was not available or executable"""

class EntropyPackageException(EntropyException):
    """Malformed or missing package data"""
