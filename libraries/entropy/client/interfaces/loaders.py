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
from entropy.const import *
from entropy.exceptions import *

class Loaders:

    __QA_cache = {}
    __security_cache = {}
    __spm_cache = {}
    def __init__(self):
        from entropy.client.interfaces.client import Client
        from entropy.client.interfaces.trigger import Trigger
        from entropy.client.interfaces.repository import Repository
        from entropy.client.interfaces.package import Package
        self.__PackageLoader = Package
        self.__RepositoryLoader = Repository
        self.__TriggerLoader = Trigger

    def closeAllQA(self):
        self.__QA_cache.clear()

    def closeAllSecurity(self):
        self.__security_cache.clear()

    def Security(self):
        chroot = etpConst['systemroot']
        cached = self.__security_cache.get(chroot)
        if cached != None:
            return cached
        from entropy.security import SecurityInterface
        cached = SecurityInterface(self)
        self.__security_cache[chroot] = cached
        return cached

    def QA(self):
        chroot = etpConst['systemroot']
        cached = self.__QA_cache.get(chroot)
        if cached != None:
            return cached
        from entropy.qa import QAInterface
        cached = QAInterface(self)
        self.__QA_cache[chroot] = cached
        return cached

    def Triggers(self, *args, **kwargs):
        return self.__TriggerLoader(self, *args, **kwargs)

    def Repositories(self, reponames = [], forceUpdate = False, noEquoCheck = False, fetchSecurity = True):
        return self.__RepositoryLoader(self, reponames = reponames,
            forceUpdate = forceUpdate, noEquoCheck = noEquoCheck,
            fetchSecurity = fetchSecurity)

    def Spm(self):
        from entropy.spm import Spm
        myroot = etpConst['systemroot']
        cached = self.__spm_cache.get(myroot)
        if cached != None: return cached
        conn = Spm(self)
        self.__spm_cache[myroot] = conn.intf
        return conn.intf

    def Package(self):
        return self.__PackageLoader(self)
