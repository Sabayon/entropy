#!/usr/bin/python -tt
# -*- coding: iso-8859-1 -*-
#    Yum Exteder (yumex) - A GUI for yum
#    Copyright (C) 2005 Tim Lauridsen < tla<AT>rasmil<DOT>DK > 
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

# Filtering action class

import yum.misc
import yum.Errors as Errors

import sre_constants
import re

        
class YumexFiltering:
    def __init__(self):
        self.filters = []

    def registerFilter(self,klass):
        if not klass in self.filters:
            self.filters.append(klass) 
            
    def processFilters(self,po):
        for flt in self.filters:
            if flt.process(po):
                continue
            else:
                return False
        return True

    def listFilters(self):
        for flt in self.filters:
            print "%s : %s " % (flt.getName(),flt._state)
            
    def get(self,name):
        for flt in self.filters:
            if flt.getName() == name:
                return flt
        return None
            
    
# Abstact Filter Classes

class YumexFilter:
    def __init__(self):
        self.name = self.getName()
        self._state = False

    def getName(self):
        return "YumexFilter"

    def process(self,po):
        raise NotImplementedError()
        
    def activate(self,state=True):
        self._state = state
        

class ListFilter(YumexFilter):
    def __init__(self):
        YumexFilter.__init__(self)
        self.fltList = []
        
    def setFilterList(self,lst):
        self.fltList = lst

    def getName(self):
        return "ListFilter"
        
    def isInList(self,value):
        if self._state:
            if value in self.fltList:
                return True
            else:
                return False
        return True

class BoolFilter(YumexFilter):
    def __init__(self):
        YumexFilter.__init__(self)
        
    def getName(self):
        return "BoolFilter"
        
    def process(self,value):
        if self._state and not value:
            return False
        else:
            return True

class ValueFilter(YumexFilter):
    def __init__(self):
        YumexFilter.__init__(self)
        self._value = None
        
    def getName(self):
        return "ValueFilter"
        
    def setValue(self,value):
        self._value = value
        
    def process(self,value):
        if self._state and not value == self._value:
            return False
        else:
            return True

# Filters

class KeywordFilter(YumexFilter):
    def __init__(self):
        YumexFilter.__init__(self)
        self.reList = []
        self.fields = ['name', 'summary', 'description']
        
    def setKeys(self,criteria):
        self.reList = []
        for string in criteria:
            restring = yum.misc.refineSearchPattern(string)
            try: 
                crit_re = re.compile(restring, flags=re.I)
                self.reList.append(crit_re)
            except sre_constants.error, e:
                raise Errors.MiscError, \
                 'Search Expression: %s is an invalid Regular Expression.\n' % string

    def getName(self):
        return "KeywordFilter"
        
    def process(self,pkg):
        if self._state: # is filter enabled ?
            for crit_re in self.reList: 
                found = False
                for field in self.fields:
                    value = pkg.getAttr( field )
                    if value and crit_re.search(value):
                        found = True
                if found:    # This search criteria was found
                    continue # Check the next one
                else:
                    return False # This criteria was not found, bail out
            return True # All search criterias was found
        else:
            return True


class RepoFilter(ListFilter):
    def getName(self):
        return "RepoFilter"
        
    def process(self,po):
        return self.isInList(po.repoid)

class ArchFilter(ListFilter):
    def getName(self):
        return "ArchFilter"
        
    def process(self,po):
        return self.isInList(po.arch)
        
class ActionFilter(ListFilter):
    def getName(self):
        return "ActionFilter"
        
    def process(self,po):
        return self.isInList(po.action)

        
class QueuedFilter(BoolFilter):
    def getName(self):
        return "QueuedFilter"
        
yumexFilter = YumexFiltering()
yumexFilter.registerFilter(RepoFilter())        
yumexFilter.registerFilter(ArchFilter())        
yumexFilter.registerFilter(KeywordFilter())
                        