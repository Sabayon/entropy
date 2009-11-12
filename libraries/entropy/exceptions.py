# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework exceptions class module}

    This module contains Entropy Framework exceptions classes.

"""
from entropy.const import const_isstring

class DumbException(Exception):
    """Dumb exception class"""

class EntropyException(Exception):
    """General superclass for Entropy exceptions"""
    def __init__(self, value):
        self.value = value[:]
        Exception.__init__(self)

    def __str__(self):
        if const_isstring(self.value):
            return self.value
        return repr(self.value)

class CorruptionError(EntropyException):
    """Corruption indication"""

class CacheCorruptionError(EntropyException):
    """On-Disk cache Corruption indication"""

class InvalidDependString(EntropyException):
    """An invalid depend string has been encountered"""

class InvalidVersionString(EntropyException):
    """An invalid version string has been encountered"""

class SecurityViolation(EntropyException):
    """An incorrect formatting was passed instead of the expected one"""

class IncorrectParameter(EntropyException):
    """A parameter of the wrong type was passed"""

class MissingParameter(EntropyException):
    """A parameter is required for the action requested but was not passed"""

class ParseError(EntropyException):
    """An error was generated while attempting to parse the request"""

class InvalidData(EntropyException):
    """An incorrect formatting was passed instead of the expected one"""

class InvalidDataType(EntropyException):
    """An incorrect type was passed instead of the expected one"""

class RepositoryError(EntropyException):
    """Cannot open repository database"""

class RepositoryPluginError(EntropyException):
    """Error during EntropyRepositoryPlugin hook execution"""

class ConnectionError(EntropyException):
    """Cannot connect to service"""

class InterruptError(EntropyException):
    """Raised to interrupt a thread or process"""

class UriHandlerNotFound(EntropyException):
    """
    Raised when URI handler (in entropy.transceivers.EntropyTransceiver)
    for given URI is not available.
    """

class FtpError(EntropyException):
    """FTP errors"""

class SystemDatabaseError(EntropyException):
    """Cannot open system database"""

class SPMError(EntropyException):
    """Source Package Manager generic errors"""

class OnlineMirrorError(EntropyException):
    """Mirror issue"""

class QueueError(EntropyException):
    """Action queue issue"""

class InvalidLocation(EntropyException):
    """
        Data was not found when it was expected to exist or
        was specified incorrectly
    """

class InvalidAtom(EntropyException):
    """Atom not properly formatted"""

class InvalidPackageSet(EntropyException):
    """Package set does not exist"""

class FileNotFound(InvalidLocation):
    """A file was not found when it was expected to exist"""

class DirectoryNotFound(InvalidLocation):
    """A directory was not found when it was expected to exist"""

class OperationNotPermitted(EntropyException):
    """An operation was not permitted operating system"""

class PermissionDenied(EntropyException):
    """Permission denied"""
    from errno import EACCES as errno

class ReadOnlyFileSystem(EntropyException):
    """Read-only file system"""

class CommandNotFound(EntropyException):
    """A required binary was not available or executable"""

class LibraryNotFound(EntropyException):
    """A required library was not available or executable"""

class SSLError(EntropyException):
    """SSL support is not available"""

class TimeoutError(EntropyException):
    """Generic Timeout Error exception"""

class EntropyPackageException(EntropyException):
    """Malformed or missing package data"""

