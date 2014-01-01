# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework repository exceptions module}.

"""

class Warning(Exception):
    """ Exception raised for important warnings like data
        truncations while inserting, etc. It must be a subclass of
        the Python StandardError (defined in the module exceptions). """

class Error(Exception):
    """ Exception that is the base class of all other error
        exceptions. You can use this to catch all errors with one
        single 'except' statement. Warnings are not considered
        errors and thus should not use this class as base. It must
        be a subclass of the Python StandardError (defined in the
        module exceptions). """

class InterfaceError(Error):
    """ Exception raised for errors that are related to the
        database interface rather than the database itself.  It
        must be a subclass of Error. """

class DatabaseError(Error):
    """ Exception raised for errors that are related to the
        database.  It must be a subclass of Error. """

class DataError(Error):
    """ Exception raised for errors that are due to problems with
        the processed data like division by zero, numeric value
        out of range, etc. It must be a subclass of DatabaseError. """

class OperationalError(Error):
    """ Exception raised for errors that are related to the
        database's operation and not necessarily under the control
        of the programmer, e.g. an unexpected disconnect occurs,
        the data source name is not found, a transaction could not
        be processed, a memory allocation error occurred during
        processing, etc.  It must be a subclass of DatabaseError. """

class IntegrityError(Error):
    """ Exception raised when the relational integrity of the
        database is affected, e.g. a foreign key check fails.  It
        must be a subclass of DatabaseError. """

class InternalError(Error):
    """ Exception raised when the database encounters an internal
        error, e.g. the cursor is not valid anymore, the
        transaction is out of sync, etc.  It must be a subclass of
        DatabaseError. """

class ProgrammingError(Error):
    """ Exception raised for programming errors, e.g. table not
        found or already exists, syntax error in the SQL
        statement, wrong number of parameters specified, etc.  It
        must be a subclass of DatabaseError. """

class NotSupportedError(Error):
    """ Exception raised in case a method or database API was used
        which is not supported by the database, e.g. requesting a
        .rollback() on a connection that does not support
        transaction or has transactions turned off.  It must be a
        subclass of DatabaseError. """

class RestartTransaction(Error):
    """ Exception raised in case the whole transaction has
        been aborted by the database and caller is kindly
        required to restart it from the beginning. """

class LockAcquireError(Exception):
    """ Raised when the repository lock, either shared or exclusive,
        cannot be acquired. """
