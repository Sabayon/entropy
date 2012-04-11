# -*- coding: utf-8 -*-
"""
Copyright (C) 2012 Fabio Erculiani

Authors:
  Fabio Erculiani

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""
from gi.repository import GObject, GLib


class PreferenceViewController(GObject.Object):

    def __init__(self, notice_store, notice_view):
        GObject.Object.__init__(self)
        self._store = notice_store
        self._view = notice_view

    def setup(self):
        """
        Setup the ConfigUpdatesViewController resources.
        """
        self._view.set_model(self._store)
        self._view.show()

    def clear(self):
        """
        Clear Configuration Updates
        """
        self._view.clear_model()

    def append(self, opaque):
        """
        Add a ConfigUpdate object to the store.
        """
        self._store.append([opaque])

    def append_many(self, opaque_list):
        """
        Append many ConfigUpdate objects to the store.
        """
        for opaque in opaque_list:
            self._store.append([opaque])

    def set_many(self, opaque_list, _from_search=None):
        """
        Set a new list of ConfigUpdate objects on the store.
        """
        self._view.clear_model()
        self.append_many(opaque_list)

    def clear_safe(self):
        """
        Thread-safe version of clear()
        """
        GLib.idle_add(self.clear)

    def append_safe(self, opaque):
        """
        Thread-safe version of append()
        """
        GLib.idle_add(self.append, opaque)

    def append_many_safe(self, opaque_list):
        """
        Thread-safe version of append_many()
        """
        GLib.idle_add(self.append_many, opaque_list)

    def set_many_safe(self, opaque_list):
        """
        Thread-safe version of set_many()
        """
        GLib.idle_add(self.set_many, opaque_list)
