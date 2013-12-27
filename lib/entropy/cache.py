# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework cache module}.

    This module contains the Entropy, asynchronous caching logic.
    It is not meant to handle cache pollution management, because
    this is either handled implicitly when cached items are pulled
    in or by using entropy.dump or cache cleaners (see
    entropy.client.interfaces.cache mixin methods)

"""
import os
import errno
import hashlib
import sys
import tempfile

from entropy.const import etpConst, const_debug_write, \
    const_debug_enabled, const_pid_exists, const_setup_perms, \
    const_mkdtemp
from entropy.core import Singleton
from entropy.misc import TimeScheduled, ParallelTask, Lifo
import time
import threading
import copy

import entropy.dump
import entropy.tools

class EntropyCacher(Singleton):

    # Max number of cache objects written at once
    _OBJS_WRITTEN_AT_ONCE = 250

    # Number of seconds between cache writeback to disk
    WRITEBACK_TIMEOUT = 5

    # If True, in-ram cache will be used to mitigate
    # concurrent push/pop executions with push() not
    # yet able to write data to disk.
    STASHING_CACHE = True

    """
    Entropy asynchronous and synchronous cache writer
    and reader. This class is a Singleton and contains
    a thread doing the cache writes asynchronously, thus
    it must be stopped before your application is terminated
    calling the stop() method.

    Sample code:

    >>> # import module
    >>> from entropy.cache import EntropyCacher
    ...
    >>> # first EntropyCacher load, start it
    >>> cacher = EntropyCacher()
    >>> cacher.start()
    ...
    >>> # now store something into its cache
    >>> cacher.push('my_identifier1', [1, 2, 3])
    >>> # now store something synchronously
    >>> cacher.push('my_identifier2', [1, 2, 3], async = False)
    ...
    >>> # now flush all the caches to disk, and make sure all
    >>> # is written
    >>> cacher.sync()
    ...
    >>> # now fetch something from the cache
    >>> data = cacher.pop('my_identifier1')
    [1, 2, 3]
    ...
    >>> # now discard all the cached (async) writes
    >>> cacher.discard()
    ...
    >>> # and stop EntropyCacher
    >>> cacher.stop()

    """

    class SemaphoreTimeScheduled(TimeScheduled):

        def __init__(self, sem, *args, **kwargs):
            self._sem = sem
            TimeScheduled.__init__(self, *args, **kwargs)

        def kill(self):
            self._sem.release()
            return TimeScheduled.kill(self)

    def init_singleton(self):
        """
        Singleton overloaded method. Equals to __init__.
        This is the place where all the properties initialization
        takes place.
        """
        self.__copy = copy
        self.__alive = False
        self.__cache_writer = None
        self.__cache_buffer = Lifo()
        self.__stashing_cache = {}
        self.__inside_with_stmt = 0
        self.__dump_data_lock = threading.Lock()
        self.__worker_sem = threading.Semaphore(0)
        # this lock ensures that all the writes are hold while it's acquired
        self.__enter_context_lock = threading.RLock()

    def __enter__(self):
        """
        When used with the with statement, pause cacher on-disk writes.
        """
        self.__enter_context_lock.acquire()
        self.__inside_with_stmt += 1

    def __exit__(self, exc_type, exc_value, traceback):
        """
        When used with the with statement, pause cacher on-disk writes.
        """
        self.__inside_with_stmt -= 1
        self.__enter_context_lock.release()

    def __copy_obj(self, obj):
        """
        Return a copy of an object done by the standard
        library "copy" module.

        @param obj: object to copy
        @type obj: any Python object
        @rtype: copied object
        @return: copied object
        """
        return self.__copy.deepcopy(obj)

    def __cacher(self, run_until_empty = False, sync = False, _loop=False):
        """
        This is where the actual asynchronous copy takes
        place. __cacher runs on a different threads and
        all the operations done by this are atomic and
        thread-safe. It just loops over and over until
        __alive becomes False.
        """
        try:
            if self.__inside_with_stmt != 0:
                return
        except AttributeError:
            # interpreter shutdown
            pass

        # make sure our set delay is respected
        try:
            self.__cache_writer.set_delay(EntropyCacher.WRITEBACK_TIMEOUT)
        except AttributeError:
            # can be None
            pass

        # sleep if there's nothing to do
        if _loop:
            try:
                # CANBLOCK
                self.__worker_sem.acquire()
                # we just consumed one acquire()
                # that was dedicated to actual data,
                # put it back
                self.__worker_sem.release()
            except AttributeError:
                pass

        def _commit_data(_massive_data):
            for (key, cache_dir), data in _massive_data:
                d_o = entropy.dump.dumpobj
                if d_o is not None:
                    d_o(key, data, dump_dir = cache_dir)

        while self.__alive or run_until_empty:

            if const_debug_enabled():
                const_debug_write(__name__,
                    "EntropyCacher.__cacher: loop: %s, alive: %s, empty: %s" % (
                        _loop, self.__alive, run_until_empty,))

            with self.__enter_context_lock:
                massive_data = []
                try:
                    massive_data_count = EntropyCacher._OBJS_WRITTEN_AT_ONCE
                except AttributeError: # interpreter shutdown
                    break
                while massive_data_count > 0:

                    if _loop:
                        # extracted an item from worker_sem
                        # call down() on the semaphore without caring
                        # can't sleep here because we're in a critical region
                        # holding __enter_context_lock
                        self.__worker_sem.acquire(False)

                    massive_data_count -= 1
                    try:
                        data = self.__cache_buffer.pop()
                    except (ValueError, TypeError,):
                        # TypeError is when objects are being destroyed
                        break # stack empty
                    massive_data.append(data)

                if not massive_data:
                    break

                task = ParallelTask(_commit_data, massive_data)
                task.name = "EntropyCacherCommitter"
                task.daemon = not sync
                task.start()
                if sync:
                    task.join()

                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "EntropyCacher.__cacher [%s], writing %s objs" % (
                            task, len(massive_data),))

                if EntropyCacher.STASHING_CACHE:
                    for (key, cache_dir), data in massive_data:
                        try:
                            del self.__stashing_cache[(key, cache_dir)]
                        except (AttributeError, KeyError,):
                            continue
                del massive_data[:]
                del massive_data

    @classmethod
    def current_directory(cls):
        """
        Return the path to current EntropyCacher cache storage directory.
        """
        return entropy.dump.D_DIR

    def start(self):
        """
        This is the method used to start the asynchronous cache
        writer but also the whole cacher. If this method is not
        called, the instance will always trash and cache write
        request.

        @return: None
        """
        self.__cache_buffer.clear()
        self.__cache_writer = EntropyCacher.SemaphoreTimeScheduled(
            self.__worker_sem, EntropyCacher.WRITEBACK_TIMEOUT,
            self.__cacher, _loop=True)
        self.__cache_writer.daemon = True
        self.__cache_writer.name = "EntropyCacheWriter"
        self.__cache_writer.set_delay_before(True)
        self.__cache_writer.start()
        while not self.__cache_writer.isAlive():
            continue
        self.__alive = True

    def is_started(self):
        """
        Return whether start is called or not. This equals to
        checking if the cacher is running, thus is writing cache
        to disk.

        @return: None
        """
        return self.__alive

    def stop(self):
        """
        This method stops the execution of the cacher, which won't
        accept cache writes anymore. The thread responsible of writing
        to disk is stopped here and the Cacher will be back to being
        inactive. A watchdog will avoid the thread to freeze the
        call if the write buffer is overloaded.

        @return: None
        """
        self.__alive = False
        if self.__cache_writer is not None:
            self.__cache_writer.kill()
            # make sure it unblocks
            self.__worker_sem.release()
            self.__cache_writer.join()
            self.__cache_writer = None
        self.sync()

    def sync(self):
        """
        This method can be called anytime and forces the instance
        to flush all the cache writes queued to disk. If wait == False
        a watchdog prevents this call to get stuck in case of write
        buffer overloads.
        """
        self.__cacher(run_until_empty = True, sync = True)

    def discard(self):
        """
        This method makes buffered cache to be discarded synchronously.

        @return: None
        """
        self.__cache_buffer.clear()
        self.__stashing_cache.clear()

    def save(self, key, data, cache_dir = None):
        """
        Save data object to cache asynchronously and in any case.
        This method guarantees that cached data is stored even if cacher
        is not started. If data cannot be stored, IOError will be raised.

        @param key: cache data identifier
        @type key: string
        @param data: picklable object
        @type data: any picklable object
        @keyword cache_dir: alternative cache directory
        @type cache_dir: string
        """
        if cache_dir is None:
            cache_dir = self.current_directory()
        try:
            with self.__dump_data_lock:
                entropy.dump.dumpobj(key, data, dump_dir = cache_dir,
                    ignore_exceptions = False)
        except (EOFError, IOError, OSError) as err:
            raise IOError("cannot store %s to %s. err: %s" % (
                key, cache_dir, repr(err)))

    def push(self, key, data, async = True, cache_dir = None):
        """
        This is the place where data is either added
        to the write queue or written to disk (if async == False)
        only and only if start() method has been called.

        @param key: cache data identifier
        @type key: string
        @param data: picklable object
        @type data: any picklable object
        @keyword async: store cache asynchronously or not
        @type async: bool
        @keyword cache_dir: alternative cache directory
        @type cache_dir: string
        """
        if not self.__alive:
            return

        if cache_dir is None:
            cache_dir = self.current_directory()

        if async:
            try:
                obj_copy = self.__copy_obj(data)
                self.__cache_buffer.push(((key, cache_dir,), obj_copy,))
                self.__worker_sem.release()
                if EntropyCacher.STASHING_CACHE:
                    self.__stashing_cache[(key, cache_dir)] = obj_copy
            except TypeError:
                # sometimes, very rarely, copy.deepcopy() is unable
                # to properly copy an object (blame Python bug)
                sys.stdout.write("!!! cannot cache object with key %s\n" % (
                    key,))
                sys.stdout.flush()
            #if const_debug_enabled():
            #   const_debug_write(__name__,
            #        "EntropyCacher.push, async push %s, into %s" % (
            #            key, cache_dir,))
        else:
            #if const_debug_enabled():
            #    const_debug_write(__name__,
            #        "EntropyCacher.push, sync push %s, into %s" % (
            #            key, cache_dir,))
            with self.__dump_data_lock:
                entropy.dump.dumpobj(key, data, dump_dir = cache_dir)

    def pop(self, key, cache_dir = None, aging_days = None):
        """
        This is the place where data is retrieved from cache.
        You must know the cache identifier used when push()
        was called.

        @param key: cache data identifier
        @type key: string
        @keyword cache_dir: alternative cache directory
        @type cache_dir: string
        @rtype: Python object
        @return: object stored into the stack or None (if stack is empty)
        """
        if cache_dir is None:
            cache_dir = self.current_directory()

        if EntropyCacher.STASHING_CACHE:
            # object is being saved on disk, it's in RAM atm
            ram_obj = self.__stashing_cache.get((key, cache_dir))
            if ram_obj is not None:
                return ram_obj

        l_o = entropy.dump.loadobj
        if not l_o:
            return
        return l_o(key, dump_dir = cache_dir, aging_days = aging_days)

    @classmethod
    def clear_cache_item(cls, cache_item, cache_dir = None):
        """
        Clear Entropy Cache item from on-disk cache.

        @param cache_item: Entropy Cache item identifier
        @type cache_item: string
        @keyword cache_dir: alternative cache directory
        @type cache_dir: string
        """
        if cache_dir is None:
            cache_dir = cls.current_directory()
        dump_path = os.path.join(cache_dir, cache_item)

        dump_dir = os.path.dirname(dump_path)
        for currentdir, subdirs, files in os.walk(dump_dir):
            path = os.path.join(dump_dir, currentdir)
            for item in files:
                if item.endswith(entropy.dump.D_EXT):
                    item = os.path.join(path, item)
                    try:
                        os.remove(item)
                    except (OSError, IOError,):
                        pass
            try:
                if not os.listdir(path):
                    os.rmdir(path)
            except (OSError, IOError,):
                pass


class MtimePingus(object):

    """
    This class can be used to store on-disk mtime of executed calls. This can
    be handy for cache expiration validation.
    Example of usage:

    >>> from entropy.cache import MtimePingus
    >>> pingus = MtimePingus()
    >>> pingus.ping("my_action_string")
    >>> pingus.pong("my_action_string)
    19501230123.0
    >>> pingus.hours_passed("my_action_string", 3)
    False
    >>> pingus.minutes_passed("my_action_string", 60)
    False
    >>> pingus seconds_passed("my_action_string", 15)
    False
    """

    PINGUS_DIR = os.path.join(etpConst['entropyworkdir'], "pingus_cache")

    def __init__(self):
        object.__init__(self)
        self.__dump_lock = threading.Lock()
        try:
            if not os.path.isdir(MtimePingus.PINGUS_DIR):
                os.makedirs(MtimePingus.PINGUS_DIR, 0o775)
                const_setup_perms(
                    MtimePingus.PINGUS_DIR,
                    etpConst['entropygid'])

        except (OSError, IOError,):
            MtimePingus.PINGUS_DIR = const_mkdtemp(
                prefix="pingus_dir")

    def _hash_key(self, key):
        """
        Create a hash representation of string.
        """
        return hashlib.sha1(key).hexdigest()

    def ping(self, action_string):
        """
        Actually store a ping action mtime.

        @param action_string: action identifier
        @type action_string: string
        """
        _hash = self._hash_key(action_string)
        with self.__dump_lock:
            entropy.dump.dumpobj(_hash, time.time(),
                dump_dir = MtimePingus.PINGUS_DIR)

    def pong(self, action_string):
        """
        Actually retrieve a ping action mtime.

        @param action_string: action identifier
        @type action_string: string
        @return: mtime (float) or None
        @rtype: float or None
        """
        _hash = self._hash_key(action_string)
        with self.__dump_lock:
            return entropy.dump.loadobj(_hash,
                dump_dir = MtimePingus.PINGUS_DIR)

    def seconds_passed(self, action_string, seconds):
        """
        Determine whether given seconds are passed since last ping against
        action_string. This also returns True if action_string does not exist.

        @param action_string: action identifier
        @type action_string: string
        @param seconds: seconds passed
        @type seconds: int
        @return: True, if seconds are passed
        @rtype: bool
        """
        mtime = self.pong(action_string)
        if mtime is None:
            return True
        return time.time() > (mtime + seconds)

    def minutes_passed(self, action_string, minutes):
        """
        Determine whether given minutes are passed since last ping against
        action_string. This also returns True if action_string does not exist.

        @param action_string: action identifier
        @type action_string: string
        @param minutes: minutes passed
        @type minutes: int
        @return: True, if minutes are passed
        @rtype: bool
        """
        mtime = self.pong(action_string)
        if mtime is None:
            return True
        return time.time() > (mtime + minutes*60)

    def hours_passed(self, action_string, hours):
        """
        Determine whether given hours are passed since last ping against
        action_string. This also returns True if action_string does not exist.

        @param action_string: action identifier
        @type action_string: string
        @param hours: minutes passed
        @type hours: int
        @return: True, if hours are passed
        @rtype: bool
        """
        mtime = self.pong(action_string)
        if mtime is None:
            return True
        return time.time() > (mtime + hours*3600)
