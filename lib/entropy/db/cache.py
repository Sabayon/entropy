# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    I{EntropyRepository} caching interface.

"""
import threading
import weakref

from entropy.core import Singleton


class EntropyRepositoryCacher(Singleton):
    """
    Tiny singleton-based helper class used by EntropyRepository in order
    to keep cached items in RAM.
    """
    def init_singleton(self):
        self.__live_cache = {}

    def clear(self):
        """
        Clear all the cached items
        """
        self.__live_cache.clear()

    def clear_key(self, key):
        """
        Clear just the cached item at key (hash table).
        """
        try:
            del self.__live_cache[key]
        except KeyError:
            pass

    def keys(self):
        """
        Return a list of available cache keys
        """
        return list(self.__live_cache.keys())

    def discard(self, key):
        """
        Discard all the cache items with hash table key starting with "key".
        """
        for dkey in tuple(self.__live_cache.keys()):
            if dkey.startswith(key):
                try:
                    self.__live_cache.pop(dkey)
                except KeyError:
                    pass

    def get(self, key):
        """
        Get the cached item, if exists.
        """
        obj = self.__live_cache.get(key)
        if isinstance(obj, weakref.ref):
            return obj()
        return obj

    def set(self, key, value, expiration_secs = None):
        """
        Set item in cache.
        """
        if isinstance(value, (set, frozenset)):
            self.__live_cache[key] = weakref.ref(value)
        else:
            self.__live_cache[key] = value

        if expiration_secs is not None:
            timer = threading.Timer(
                expiration_secs,
                self.__live_cache.pop,
                args = (key, None))
            timer.name = "EntropyRepositoryCacher.TimedPop"
            timer.daemon = True
            timer.start()
