# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

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
from __future__ import with_statement
from entropy.core import Singleton
from entropy.misc import TimeScheduled, Lifo
import time

class EntropyCacher(Singleton):

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    import threading
    def init_singleton(self):
        self.__alive = False
        self.__CacheWriter = None
        self.__CacheBuffer = Lifo()
        self.__CacheLock = self.threading.Lock()
        import copy
        self.copy = copy

    def __copy_obj(self, obj):
        return self.copy.deepcopy(obj)

    def __cacher(self):
        while 1:
            if not self.__alive: break
            with self.__CacheLock:
                data = self.__CacheBuffer.pop()
            if data == None: break
            key, data = data
            d_o = self.dumpTools.dumpobj
            if not d_o: break
            d_o(key,data)

    def __del__(self):
        self.stop()

    def start(self):
        self.__CacheWriter = TimeScheduled(1,self.__cacher)
        self.__CacheWriter.set_delay_before(True)
        self.__CacheWriter.start()
        while not self.__CacheWriter.isAlive():
            continue
        self.__alive = True

    def sync(self, wait = False):
        if not self.__alive: return
        wd = 10
        while self.__CacheBuffer.is_filled() and ((wd > 0) or wait):
            if not wait: wd -= 1
            time.sleep(0.5)

    def push(self, key, data, async = True):
        if not self.__alive: return
        if async:
            with self.__CacheLock:
                self.__CacheBuffer.push((key,self.__copy_obj(data),))
        else:
            self.dumpTools.dumpobj(key,data)

    def pop(self, key):
        with self.__CacheLock:
            l_o = self.dumpTools.loadobj
            if not l_o: return
            return l_o(key)

    def stop(self):
        if not self.__alive: return
        if self.__CacheBuffer and self.__alive:
            wd = 20
            while self.__CacheBuffer.is_filled() and wd:
                wd -= 1
                time.sleep(0.5)
            self.__CacheBuffer.clear()
        if self.__CacheWriter != None:
            self.__CacheWriter.kill()
            self.__CacheWriter.join()
        self.__alive = False
