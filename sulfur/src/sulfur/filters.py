#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
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

from entropy.const import etpUi
from entropy.output import print_generic

class Filtering:

    def __init__(self):
        self.filters = []

    def registerFilter(self, klass):
        if not klass in self.filters:
            self.filters.append(klass)

    def processFilters(self, po):
        for flt in self.filters:
            if flt.process(po):
                continue
            else:
                return False
        return True

    def listFilters(self):
        for flt in self.filters:
            print_generic("%s : %s " % (flt.get_name(), flt._state))

    def get(self, name):
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

    def process(self, po):
        raise NotImplementedError()

    def activate(self,state=True):
        self._state = state

class KeywordFilter(BaseFilter):

    def __init__(self):
        BaseFilter.__init__(self)
        self.keywordList = []
        self.fields = ['name']
        self.pkgGroups = {}
        self.groupCats = set()

    def setKeys(self, criteria, pkg_groups):

        del self.fields[:]
        self.fields.extend(['name'])
        del self.keywordList[:]

        self.groupCats.clear()
        self.pkgGroups.clear()
        self.keywordList.extend([x.lower() for x in criteria])
        self.pkgGroups.update(pkg_groups)
        for crit in self.keywordList:
            if crit in self.pkgGroups:
                self.groupCats.update(self.pkgGroups[crit]['categories'])

    def get_name(self):
        return "KeywordFilter"

    def process(self, pkg):

        if pkg.dummy_type is not None:
            return False

        if not self._state:
            # is filter disabled ?
            return True

        for crit in self.keywordList:

            if crit in self.pkgGroups:

                cat = pkg.cat
                if cat in self.groupCats:
                    return True
                return False

            else:

                for field in self.fields:
                    try:
                        value = getattr(pkg, field)
                    except:
                        if etpUi['debug']:
                            raise
                    if not value:
                        continue
                    if value.lower().find(crit) != -1:
                        return True
                    return False

        return False

Filter = Filtering()
Filter.registerFilter(KeywordFilter())
