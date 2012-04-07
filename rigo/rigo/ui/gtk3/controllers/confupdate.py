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
from gi.repository import GObject

from rigo.ui.gtk3.widgets.notifications import \
    ConfigUpdatesNotificationBox

class ConfigUpdatesViewController(GObject.Object):

    def __init__(self, entropy_client, config_store, config_view):
        GObject.Object.__init__(self)
        self._entropy = entropy_client
        self._store = config_store
        self._view = config_view
        self._nc = None
        self._avc = None

    def setup(self):
        """
        Setup the ConfigUpdatesViewController resources.
        """
        self._view.set_model(self._store)
        self._view.show()

    def set_notification_controller(self, nc):
        """
        Bind a UpperNotificationViewController to this class.
        """
        self._nc = nc

    def set_applications_controller(self, avc):
        """
        Bind an ApplicationsViewController object to this class.
        """
        self._avc = avc

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

    def notify_updates(self, config_updates):
        """
        Notify Configuration File Updates to User.
        """
        # setup store
        self.set_many(config_updates)
        if self._nc is not None and self._avc is not None:
            box = ConfigUpdatesNotificationBox(
                self._entropy, self._avc, len(config_updates))
            self._nc.append(box)
