# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

"""
import errno
import fcntl

from threading import Lock


class MatterResourceLock(object):
    """
    This class exposes a Lock-like interface for acquiring Matter lock file.
    """

    LOCK_FILE_PATH = "/var/tmp/.matter_resource.lock"

    class NotAcquired(Exception):
        """ Raised when Lock cannot be acquired """

    def __init__(self, blocking):
        """
        MatterResourceLock constructor.

        @param blocking: acquire lock in blocking mode?
        @type blocking: bool
        """
        self._blocking = blocking
        self.__inside_with_stmt = 0
        self.__lock_f = None
        self.__call_lock = Lock()

    def acquire(self):
        """
        Acquire the lock file.
        """
        file_path = MatterResourceLock.LOCK_FILE_PATH
        if self._blocking:
            flags = fcntl.LOCK_EX | fcntl.LOCK_NB
        else:
            flags = fcntl.LOCK_EX

        with self.__call_lock:
            if self.__lock_f is None:
                self.__lock_f = open(file_path, "wb")
                try:
                    fcntl.flock(self.__lock_f.fileno(), flags)
                except IOError as err:
                    if err.errno not in (errno.EACCES, errno.EAGAIN,):
                        # ouch, wtf?
                        raise
                    raise MatterResourceLock.NotAcquired(
                        "unable to acquire lock")

    def release(self):
        with self.__call_lock:
            if self.__lock_f is not None:
                fcntl.flock(self.__lock_f.fileno(), fcntl.LOCK_UN)
                self.__lock_f.close()
                self.__lock_f = None

    def __enter__(self):
        """
        Acquire lock. Not thread-safe.
        """
        if self.__inside_with_stmt < 1:
            self.acquire()
        self.__inside_with_stmt += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Release lock. Not thread-safe.
        """
        self.__inside_with_stmt -= 1
        if self.__inside_with_stmt < 1:
            self.release()
