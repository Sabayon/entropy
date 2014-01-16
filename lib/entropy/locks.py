# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy resources lock functions module}.

"""
import contextlib
import errno
import fcntl
import threading
import os

from entropy.cache import EntropyCacher
from entropy.const import etpConst, const_setup_directory, const_setup_file, \
    const_debug_write
from entropy.core.settings.base import SystemSettings
from entropy.i18n import _
from entropy.misc import FlockFile
from entropy.output import TextInterface, blue, darkred, darkgreen, teal


class SimpleFileLock(object):
    """
    Helper class that makes it easy to acquire and release file based locks.
    """

    @classmethod
    def acquire(cls, lock_file, lock_map):
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
    def release(cls, lock_file, lock_map):
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


class ResourceLock(object):
    """
    Generic Entropy Resource Lock abstract class.
    """

    _TLS = threading.local()

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
        raise NotImplementedError()

    def is_already_acquired(self):
        """
        Return whether the current thread has already acquired the
        lock (which is reentrant).
        """
        mapped = self._file_lock_setup()
        return mapped['recursed']

    def _file_lock_setup(self):
        """
        Setup the locking status dict for self.path().
        """
        lock_map = getattr(self._TLS, "lock_map", None)
        if lock_map is None:
            lock_map = {}
            self._TLS.lock_map = lock_map

        file_path = self.path()
        mapped = lock_map.get(file_path)
        if mapped is None:
            mapped = {
                'count': 0,
                'ref': None,
                'path': file_path,
                'shared': None,
                'recursed': False,
            }
            lock_map[file_path] = mapped
        return mapped

    def _lock_resource(self, blocking, shared):
        """
        Internal function that does the locking given a lock
        file path.
        """
        mapped = self._file_lock_setup()

        # I asked for an exclusive lock, but
        # I am only holding a shared one, don't
        # return True.
        want_exclusive_when_shared = not shared and mapped['shared']

        if mapped['ref'] is not None:
            if not want_exclusive_when_shared:
                # reentrant lock, already acquired
                mapped['count'] += 1
                return True

        else:
            mapped['shared'] = shared

        # watch for deadlocks using TLS
        if mapped['recursed'] and want_exclusive_when_shared:
            # deadlock, raise exception
            raise RuntimeError(
                "want exclusive lock when shared acquired")

        # not the same thread requested an exclusive lock when shared
        mapped['recursed'] = True
        # fall through, we won't deadlock

        path = mapped['path']

        acquired, flock_f = self._file_lock_create(
            path, blocking=blocking, shared=shared)

        if acquired:
            mapped['count'] += 1
            if flock_f is not None:
                mapped['ref'] = flock_f

        return acquired

    def _unlock_resource(self):
        """
        Internal function that does the unlocking of a given
        lock file.
        """
        mapped = self._file_lock_setup()

        if mapped['count'] == 0:
            raise RuntimeError("releasing a non-acquired lock")

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

        # allow the same thread to acquire the lock again.
        mapped['recursed'] = False

    def _file_lock_create(self, lock_path, blocking=False, shared=False):
        """
        Create and allocate the lock file pointed by lock_data structure.
        """
        lock_dir = os.path.dirname(lock_path)
        try:
            const_setup_directory(lock_dir)
        except OSError as err:
            const_debug_write(
                __name__, "Error in const_setup_directory %s: %s" % (
                    lock_dir, err))
            # we may just not have the perms to create the dir.
            if err.errno != errno.EPERM:
                raise

        try:
            fmode = 0o664
            if shared:
                fd = os.open(lock_path, os.O_CREAT | os.O_RDONLY, fmode)
            else:
                fd = os.open(lock_path, os.O_CREAT | os.O_APPEND, fmode)
        except OSError as err:
            if err.errno in (errno.ENOENT, errno.EACCES):
                # cannot get lock or dir doesn't exist
                return False, None
            raise

        # ensure that entropy group can write on that
        try:
            const_setup_file(lock_path, etpConst['entropygid'], 0o664)
        except OSError:
            pass

        acquired = False
        flock_f = None
        try:
            flock_f = FlockFile(lock_path, fd=fd)
            if blocking:
                if shared:
                    flock_f.acquire_shared()
                else:
                    flock_f.acquire_exclusive()
                acquired = True
                return True, flock_f

            # non blocking
            if shared:
                acquired = flock_f.try_acquire_shared()
            else:
                acquired = flock_f.try_acquire_exclusive()
            if not acquired:
                return False, None
            return True, flock_f

        except Exception:
            if flock_f is not None:
                try:
                    flock_f.close()
                except (OSError, IOError):
                    pass
                flock_f = None
            raise

        finally:
            if not acquired and flock_f is not None:
                try:
                    flock_f.close()
                except (OSError, IOError):
                    pass
                flock_f = None

    def _wait_resource(self, shared):
        """
        Try to acquire the resource, on failure, print a warning
        and block until acquired.
        """
        if shared:
            acquired = self.try_acquire_shared()
        else:
            acquired = self.try_acquire_exclusive()

        if acquired:
            return True

        if shared:
            msg = "%s %s ..." % (
                blue(_("Acquiring shared lock on")),
                darkgreen(self.path()),)
        else:
            msg = "%s %s ..." % (
                blue(_("Acquiring exclusive lock on")),
                darkgreen(self.path()),)

        self._out.output(
            msg,
            importance=0,
            back=True,
            level="warning"
        )

        if shared:
            self.acquire_shared()
        else:
            self.acquire_exclusive()
        return True

    @contextlib.contextmanager
    def exclusive(self):
        """
        Acquire an exclusive file lock for this repository (context manager).
        """
        self.wait_exclusive()
        try:
            yield
        finally:
            self.release()

    def acquire_exclusive(self):
        """
        Acquire the resource in exclusive blocking mode.
        """
        self._lock_resource(True, False)

    def try_acquire_exclusive(self):
        """
        Acquire the resource in exclusive non-blocking mode.
        Return True if resource is acquired, False otherwise.
        """
        return self._lock_resource(False, False)

    def wait_exclusive(self):
        """
        Try to acquire the resource in non-blocking mode, on
        failure, print a warning and then acquire the resource
        in blocking mode.
        """
        return self._wait_resource(False)

    @contextlib.contextmanager
    def shared(self):
        """
        Acquire a shared file lock for this repository (context manager).
        """
        self.wait_shared()
        try:
            yield
        finally:
            self.release()

    def acquire_shared(self):
        """
        Acquire the resource in shared blocking mode.
        """
        self._lock_resource(True, True)

    def try_acquire_shared(self):
        """
        Acquire the resource in shared non-blocking mode.
        Return True if resource is acquired, False otherwise.
        """
        return self._lock_resource(False, True)

    def wait_shared(self):
        """
        Try to acquire the resource in non-blocking mode, on
        failure, print a warning and then acquire the resource
        in blocking mode.
        """
        return self._wait_resource(True)

    def release(self):
        """
        Release the previously acquired resource.
        """
        self._unlock_resource()


class EntropyResourcesLock(ResourceLock):
    """
    Entropy Resources Lock (or Big Entropy Lock, BEL) class.

    This class wraps the interface to the Entropy Resources Lock,
    for acquiring shared or exclusive access to the Entropy Package
    Manager.

    Typically, routines acquire this lock in shared mode and
    only a handful of code paths require exclusive locking.
    """

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
        super(EntropyResourcesLock, self).__init__(
            output=output)

    def path(self):
        """
        Return the path to the lock file.
        """
        return os.path.join(etpConst['entropyworkdir'],
                            '.using_resources')

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

    def _lock_resource(self, blocking, shared):
        """
        Overridden from ResourceLock.
        Add hooks support code.
        """
        acquired = super(EntropyResourcesLock, self)._lock_resource(
            blocking, shared)
        if acquired:
            self._clear_resources_after_lock()
        return acquired


class UpdatesNotificationResourceLock(ResourceLock):
    """
    This lock can be used to temporarily stop updates availability
    notifications (like those sent by RigoDaemon) from taking
    place. For instance, it is possible to acquire this lock in shared
    mode in order to stop RigoDaemon from signaling the availability
    of updates during an upgrade performed by Equo.  RigoDaemon
    acquires the lock in exclusive NB mode for a short period of time
    in order to ensure that it can signal updates availability.

    If you want to run an install queue, acquire this in shared mode,
    if you want to notify available updates, try to acquire this in
    exclusive mode.
    """

    def __init__(self, output=None):
        """
        Object constructor.

        @keyword output: a TextInterface interface
        @type output: entropy.output.TextInterface or None
        """
        super(UpdatesNotificationResourceLock, self).__init__(
            output=output)

    def path(self):
        """
        Return the path to the lock file.
        """
        return os.path.join(etpConst['entropyrundir'],
                            '.entropy.locks.SystemNotifications.lock')
