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

class StatusInterface(dict):

    def __init__(self):
        self.__last_mirrorname = None
        dict.__init__(self)

    def add_failing_mirror(self, mirrorname, increment = 1):
        if not self.has_key(mirrorname):
            self[mirrorname] = 0
        self[mirrorname] += increment
        return self[mirrorname]

    def get_failing_mirror_status(self, mirrorname):
        return self.get(mirrorname,0)

    def set_failing_mirror_status(self, mirrorname, value):
        self[mirrorname] = value

    def set_working_mirror(self, mirrorname):
        self.__last_mirrorname = mirrorname

    def add_failing_working_mirror(self, value):
        if self.__last_mirrorname:
            self.add_failing_mirror(self.__last_mirrorname, value)

    def clear(self):
        self.__last_mirrorname = None
        return dict.clear(self)