#!/usr/bin/python2 -O
# -*- coding: iso-8859-1 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
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


class Filtering:

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
            print "%s : %s " % (flt.get_name(),flt._state)

    def get(self,name):
        for flt in self.filters:
            if flt.get_name() == name:
                return flt
        return None


class BaseFilter:

    def __init__(self):
        self.name = self.get_name()
        self._state = False

    def get_name(self):
        return "BaseFilter"

    def process(self,po):
        raise NotImplementedError()

    def activate(self,state=True):
        self._state = state

class KeywordFilter(BaseFilter):

    def __init__(self):
        BaseFilter.__init__(self)
        self.keywordList = []
        self.fields = ['name']#, 'description']

    def setKeys(self,criteria):
        self.keywordList = criteria[:]

    def get_name(self):
        return "KeywordFilter"

    def process(self,pkg):
        if pkg.dummy_type != None: return False
        if self._state: # is filter enabled ?
            for crit in self.keywordList:
                found = False
                for field in self.fields:
                    value = getattr(pkg,field)
                    if not value: continue
                    if value.lower().find(crit.lower()) != -1:
                        found = True
                if found:    # This search criteria was found
                    continue # Check the next one
                else:
                    return False # This criteria was not found, bail out
            return True # All search criterias was found
        else:
            return True

Filter = Filtering()
Filter.registerFilter(KeywordFilter())
