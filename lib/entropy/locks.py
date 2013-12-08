# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy resources lock functions module}.

"""
import errno
import fcntl
import threading
import time
import os

from entropy.cache import EntropyCacher
from entropy.const import etpConst, const_setup_directory, const_setup_file
from entropy.core.settings.base import SystemSettings
from entropy.i18n import _
from entropy.misc import FlockFile
from entropy.output import TextInterface, blue, darkred, teal


class SimpleFileLock(object):
    """
    Helper class that makes it easy to acquire and release file based locks.
    """

    @classmethod
    def acquire_lock(cls, lock_file, lock_map):
        """
        Make possible to protect a code region using an EXCLUSIVE, non-blocking
        file lock. A lock map (dict) is required in order to register the lock
        data (usually lock file object) and then unlock it using release_lock().

        @param lock_file: path to lock file used for locking
        @type lock_file: string
        @param lock_map: lock map (dict object) that can be used to
            record the lock data in order to unlock it on release_lock().
        @type lock_map: dict
        @return: True, if lock has been acquired, False otherwise
        @rtype: bool
        """
        lock_f = open(lock_file, "a+")
        try:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_f.truncate()
            lock_f.write(str(os.getpid()))
            lock_f.flush()
            lock_map[lock_file] = lock_f
            return True
        except IOError as err:
            lock_f.close()
            if err.errno not in (errno.EACCES, errno.EAGAIN,):
                # ouch, wtf?
                raise
            return False # lock already acquired
        except Exception:
            lock_f.close()
            raise

    @classmethod
    def release_lock(cls, lock_file, lock_map):
        """
        Release a previously acquired lock through acquire_lock().

        @param lock_file: path to lock file used for locking
        @type lock_file: string
        @param lock_map: lock map (dict object) that can be used to
            record the lock data in order to unlock it on release_lock().
        @type lock_map: dict
        """
        try:
            lock_f = lock_map.pop(lock_file)
        except KeyError:
            lock_f = None

        if lock_f is not None:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
            lock_f.close()

        try:
            os.remove(lock_file)
        except OSError as err:
            # cope with possible race conditions
            if err.errno != errno.ENOENT:
                raise


class EntropyResourcesLock(object):
    """
    Entropy Resources Lock (or Big Entropy Lock, BEL) class.

    This class wraps the interface to the Entropy Resources Lock,
    for acquiring shared or exclusive access to the Entropy Package
    Manager.

    Typically, routines acquire this lock in shared mode and
    only a handful of code paths require exclusive locking.
    """

    _FILE_LOCK_MUTEX = threading.Lock()
    _FILE_LOCK_MAP = {}

    # List of callables that will be triggered upon lock acquisition.
    # It can be used to execute cache cleanups.
    _POST_ACQUIRE_HOOK_LOCK = threading.Lock()
    _POST_ACQUIRE_HOOKS = {}
    _POST_ACQUIRE_HOOK_COUNT = 0

    @classmethod
    def add_post_acquire_hook(cls, callab):
        """
        Add a hook that will be executed once the lock is acquired.
        This can be used to execute cache cleanups or other activities
        of the same sort. The callable is called with the EntropyCacher
        lock held.

        This method returns a reference number that must be used to perform
        the removal of the hook.
        """
        with EntropyResourcesLock._POST_ACQUIRE_HOOK_LOCK:
            EntropyResourcesLock._POST_ACQUIRE_HOOK_COUNT += 1
            index = EntropyResourcesLock._POST_ACQUIRE_HOOK_COUNT
            EntropyResourcesLock._POST_ACQUIRE_HOOKS[index] = callab

        return index

    @classmethod
    def remove_post_acquire_hook(cls, index):
        """
        Remove a previously added hook using its reference.

        This method raises KeyError if the hook is not present.
        """
        with EntropyResourcesLock._POST_ACQUIRE_HOOK_LOCK:
            EntropyResourcesLock._POST_ACQUIRE_HOOKS.pop(index)

    def __init__(self, output=None):
        """
        Object constructor.

        @keyword output: a TextInterface interface
        @type output: entropy.output.TextInterface or None
        """
        if output is not None:
            self._out = output
        else:
            self._out = TextInterface

    def path(self):
        """
        Return the path to the lock file.
        """
        return os.path.join(etpConst['entropyworkdir'],
                            '.using_resources')

    def _file_lock_setup(self, file_path):
        """
        Setup _FILE_LOCK_MAP for file_path, allocating locking information.
        """
        mapped = EntropyResourcesLock._FILE_LOCK_MAP.get(file_path)
        if mapped is None:
            mapped = {
                'count': 0,
                'ref': None,
                'path': file_path,
            }
            EntropyResourcesLock._FILE_LOCK_MAP[file_path] = mapped
        return mapped

    def _lock_resource(self, blocking, shared):
        """
        Internal function that does the locking given a lock
        file path.
        """
        lock_path = self.path()

        with EntropyResourcesLock._FILE_LOCK_MUTEX:
            mapped = self._file_lock_setup(lock_path)
            if mapped['ref'] is not None:
                # reentrant lock, already acquired
                mapped['count'] += 1
                return True
            path = mapped['path']

        acquired, flock_f = self._file_lock_create(
            path, blocking = blocking, shared = shared)

        if acquired:
            self._clear_resources_after_lock()

            with EntropyResourcesLock._FILE_LOCK_MUTEX:
                mapped['count'] += 1
                if flock_f is not None:
                    mapped['ref'] = flock_f
        return acquired

    def _promote_resource(self, blocking):
        """
        Internal function that does the file lock promotion.
        """
        lock_path = self.path()

        with EntropyResourcesLock._FILE_LOCK_MUTEX:
            mapped = self._file_lock_setup(lock_path)
            flock_f = mapped['ref']
            if flock_f is None:
                # wtf ?
                raise IOError("not acquired")

        acquired = True
        if blocking:
            flock_f.promote()
        else:
            acquired = flock_f.try_promote()
        return acquired

    def _unlock_resource(self):
        """
        Internal function that does the unlocking of a given
        lock file.
        """
        lock_path = self.path()
        with EntropyResourcesLock._FILE_LOCK_MUTEX:
            mapped = self._file_lock_setup(lock_path)
            # decrement lock counter
            if mapped['count'] > 0:
                mapped['count'] -= 1
            # if lock counter > 0, still locked
            # waiting for other upper-level calls
            if mapped['count'] > 0:
                return

            ref_obj = mapped['ref']
            if ref_obj is not None:
                # do not remove!
                ref_obj.release()
                ref_obj.close()
                mapped['ref'] = None

    def _file_lock_create(self, pidfile, blocking = False, shared = False):
        """
        Create and allocate the lock file pointed by lock_data structure.
        """
        lockdir = os.path.dirname(pidfile)
        try:
            os.makedirs(lockdir, 0o775)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        const_setup_directory(lockdir)

        try:
            pid_f = open(pidfile, "a+")
        except IOError as err:
            if err.errno in (errno.ENOENT, errno.EACCES):
                # cannot get lock or dir doesn't exist
                return False, None
            raise

        # ensure that entropy group can write on that
        try:
            const_setup_file(pidfile, etpConst['entropygid'], 0o664)
        except OSError:
            pass

        flock_f = FlockFile(pidfile, fobj = pid_f)
        if blocking:
            if shared:
                flock_f.acquire_shared()
            else:
                flock_f.acquire_exclusive()
        else:
            acquired = False
            if shared:
                acquired = flock_f.try_acquire_shared()
            else:
                acquired = flock_f.try_acquire_exclusive()
            if not acquired:
                return False, None

        return True, flock_f

    def _clear_resources_after_lock(self):
        """
        Clear resources that could have become stale after
        the Entropy Lock acquisition.
        """
        cacher = EntropyCacher()
        with cacher:

            SystemSettings().clear()
            cacher.discard()

            with EntropyResourcesLock._POST_ACQUIRE_HOOK_LOCK:
                callables = list(
                    EntropyResourcesLock._POST_ACQUIRE_HOOKS.values()
                )

            for callab in callables:
                callab()

        cacher.sync()

    def _wait_resource(self, lock_func, sleep_seconds = 1.0,
                       max_lock_count = 300, shared = False,
                       spinner = False):
        """
        Poll on a given resource hoping to get its lock.
        """
        lock_count = 0
        # check lock file
        while True:
            acquired = lock_func(blocking=False, shared=shared)
            if acquired:
                if lock_count > 0:
                    self._out.output(
                        blue(_("Resources unlocked, let's go!")),
                        importance = 1,
                        level = "info",
                        header = darkred(" @@ ")
                    )
                break

            if spinner:
                header = teal("|/-\\"[lock_count % 4] + " ")
                count = None
            else:
                header = darkred(" @@ ")
                count = (lock_count + 1, max_lock_count)

            if lock_count >= max_lock_count and not spinner:
                self._out.output(
                    blue(_("Resources still locked, giving up!")),
                    importance = 1,
                    level = "warning",
                    header = header
                )
                return True # gave up

            lock_count += 1
            self._out.output(
                blue(_("Resources locked, sleeping...")),
                importance = 1,
                level = "warning",
                header = header,
                back = True,
                count = count
            )
            time.sleep(sleep_seconds)
        return False # yay!

    def lock_resources(self, blocking = False, shared = False):
        """
        Acquire Entropy Resources lock; once acquired, it's possible
        to alter:
        - Installed Packages Repository
        - Available Packages Repositories
        - Entropy Configuration and metadata
        If shared=True, you are likely calling this method as user, if
        so, make sure that the same is in the "entropy" group, by
        using entropy.tools.is_user_in_entropy_group().

        @keyword blocking: execute in blocking mode?
        @type blocking: bool
        @keyword shared: acquire a shared lock? (default is False)
        @type shared: bool
        @return: True, if lock has been acquired. False otherwise.
        @rtype: bool
        """
        return self._lock_resource(blocking, shared)

    def promote_resources(self, blocking = False):
        """
        Promote previously acquired Entropy Resources Lock from
        shared to exclusive.

        @keyword blocking: execute in blocking mode?
        @type blocking: bool
        """
        return self._promote_resource(blocking)

    def unlock_resources(self):
        """
        Release previously locked Entropy Resources, see lock_resources().
        """
        return self._unlock_resource()

    def wait_resources(self, sleep_seconds = 1.0, max_lock_count = 300,
                       shared = False, spinner = False):
        """
        Wait until Entropy resources are unlocked.
        This method polls over the available repositories lock and
        could run into starvation.

        @keyword sleep_seconds: time between checks
        type sleep_seconds: float
        @keyword max_lock_count: maximum number of times the lock is checked
        @type max_lock_count: int
        @keyword shared: acquire a shared lock? (default is False)
        @type shared: bool
        @keyword spinner: if True, a spinner will be used to wait indefinitely
            and max_lock_count will be ignored in non-blocking mode.
        @type spinner: bool
        @return: True, if lock hasn't been released, False otherwise.
        @rtype: bool
        """
        return self._wait_resource(
            self.lock_resources, sleep_seconds=sleep_seconds,
            max_lock_count=max_lock_count, shared=shared,
            spinner=spinner)
