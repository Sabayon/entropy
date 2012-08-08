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
import os
import hashlib
import errno

from gi.repository import Gtk, GObject, GLib

from rigo.enums import Icons, RigoViewStates
from rigo.utils import prepare_markup
from rigo.models.preference import Preference
from rigo.models.group import Group

from entropy.const import const_debug_write
from entropy.misc import ParallelTask


class GroupViewController(GObject.Object):

    def __init__(self, rigo_service, group_store, group_view, prefc):
        GObject.Object.__init__(self)
        self._service = rigo_service
        self._store = group_store
        self._view = group_view
        self._prefc = prefc
        self._avc = None

    def load(self):
        """
        Request a content (re)load.
        """
        const_debug_write(
            __name__, "GroupVC: load() called")
        def _load():
            groups = self._service.groups()
            objs = []
            for identifier, data in groups.items():
                group = Group(
                    self._avc, identifier, data['name'],
                    data['description'],
                    data['categories'])
                objs.append(group)
            self.set_many_safe(objs)

        task = ParallelTask(_load)
        task.name = "OnGroupLoadRequest"
        task.daemon = True
        task.start()

    def _show(self):
        """
        Show Application Groups interface, if possible.
        """
        if self._avc is not None:
            GLib.idle_add(self._avc.emit, "view-want-change",
                          RigoViewStates.GROUPS_VIEW_STATE,
                          None)

    def set_applications_controller(self, avc):
        """
        Bind an ApplicationsViewController object to this class.
        """
        self._avc = avc

    def setup(self):
        """
        Setup the GroupViewController resources.
        """
        self._view.set_model(self._store)
        pref = Preference(
            -100,
            _("Application Groups"),
            _("Show Application Groups."),
            Icons.GROUPS, self._show)
        self._prefc.append(pref)

        self._view.show()

    def clear(self):
        """
        Clear Repository List
        """
        self._view.clear_model()

    def append(self, opaque):
        """
        Add a Repository object to the store.
        """
        self._store.append([opaque])

    def append_many(self, opaque_list):
        """
        Append many Repository objects to the store.
        """
        for opaque in opaque_list:
            self._store.append([opaque])

    def set_many(self, opaque_list):
        """
        Set a new list of Repository objects on the store.
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
