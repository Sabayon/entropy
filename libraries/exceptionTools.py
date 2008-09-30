#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy exceptions class

    Copyright (C) 2007-2008 Fabio Erculiani
    
    structure inspired from portage_exception.py
    Copyright 1998-2004 Gentoo Foundation
    # $Id: portage_exception.py 6885 2007-06-20 05:45:31Z zmedico $

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

class EntropyException(Exception):
    """General superclass for Entropy exceptions"""
    def __init__(self,value):
        self.value = value[:]

    def __str__(self):
        if isinstance(self.value, basestring):
            return self.value
        else:
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

class ConnectionError(EntropyException):
        """Cannot connect to service"""

class NotImplementedError(EntropyException):
        """Feature not implemented"""

class InterruptError(EntropyException):
        """Raised to interrupt a thread or process"""

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
        """Data was not found when it was expected to exist or was specified incorrectly"""

class InvalidAtom(EntropyException):
        """Atom not properly formatted"""

class FileNotFound(InvalidLocation):
        """A file was not found when it was expected to exist"""

class DirectoryNotFound(InvalidLocation):
        """A directory was not found when it was expected to exist"""

class OperationNotPermitted(EntropyException):
        """An operation was not permitted operating system"""

class PermissionDenied(EntropyException):
        from errno import EACCES as errno
        """Permission denied"""

class ReadOnlyFileSystem(EntropyException):
        """Read-only file system"""

class CommandNotFound(EntropyException):
        """A required binary was not available or executable"""

class LibraryNotFound(EntropyException):
        """A required library was not available or executable"""

class SSLError(EntropyException):
        """SSL support is not available"""

class EntropyPackageException(EntropyException):
        """Malformed or missing package data"""

class SystemError(EntropyException):
        """General System Error"""