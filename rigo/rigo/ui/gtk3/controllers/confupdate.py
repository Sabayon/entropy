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
from gi.repository import GObject, Gtk, GLib

from threading import Lock

from rigo.ui.gtk3.widgets.notifications import \
    ConfigUpdatesNotificationBox, NotificationBox
from rigo.utils import prepare_markup

from entropy.i18n import _
from entropy.const import const_debug_write
from entropy.misc import ParallelTask

class ConfigUpdatesViewController(GObject.Object):

    __gsignals__ = {
        # View has been cleared
        "view-cleared" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
        # View has been filled
        "view-filled" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
    }

    def __init__(self, entropy_client, config_store, config_view):
        GObject.Object.__init__(self)
        self._entropy = entropy_client
        self._store = config_store
        self._view = config_view
        self._nc = None
        self._avc = None
        self._box = None
        self._box_mutex = Lock()

    def _notify_error(self, message):
        """
        Notify a generic configuration management action error.
        """
        box = NotificationBox(
            prepare_markup(message),
            message_type=Gtk.MessageType.ERROR,
            context_id="ConfigUpdateErrorContextId")
        self._nc.append(box, timeout=10)

    def _remove_path(self, path):
        """
        Remove the given object path from model
        """
        iterator = self._store.get_iter(path)
        if iterator is not None:
            self._store.remove(iterator)
            if not self._store.get_iter_first():
                # done removing stuff, hide view
                self.emit("view-cleared")
                with self._box_mutex:
                    box = self._box
                    if box is not None and self._nc is not None:
                        self._nc.remove(box)
                        self._box = None

    def _on_source_edit(self, widget, path, cu):
        """
        Source File Edit request.
        """
        const_debug_write(__name__, "Confc: _on_source_edit: %s" % (cu,))
        def _edit():
            if not cu.edit():
                def _notify():
                    msg = "%s: <i>%s</i>" % (
                        _("Cannot <b>edit</b> configuration file"),
                        cu.source(),)
                    self._notify_error(msg)
                GLib.idle_add(_notify)

        task = ParallelTask(_edit)
        task.name = "OnSourceEdit"
        task.daemon = True
        task.start()

    def _on_show_diff(self, widget, path, cu):
        """
        Diff request.
        """
        const_debug_write(__name__, "Confc: _on_show_diff: %s" % (cu,))
        def _diff():
            if not cu.diff():
                def _notify():
                    msg = "%s: <i>%s</i>" % (
                        _("Cannot <b>show</b> configuration "
                          "files difference"),
                        cu.source(),)
                    self._notify_error(msg)
                GLib.idle_add(_notify)

        task = ParallelTask(_diff)
        task.name = "OnShowDiff"
        task.daemon = True
        task.start()

    def _on_source_merge(self, widget, path, cu):
        """
        Source file merge request.
        """
        const_debug_write(__name__, "Confc: _on_source_merge: %s" % (cu,))
        def _merge():
            if not cu.merge():
                def _notify():
                    msg = "%s: <i>%s</i>" % (
                        _("Cannot <b>merge</b> configuration file"),
                        cu.source(),)
                    self._notify_error(msg)
                GLib.idle_add(_notify)
            else:
                GLib.idle_add(self._remove_path, path)

        task = ParallelTask(_merge)
        task.name = "OnSourceMerge"
        task.daemon = True
        task.start()

    def _on_source_discard(self, widget, path, cu):
        """
        Source file discard request.
        """
        const_debug_write(
            __name__, "Confc: _on_source_discard: %s" % (cu,))
        def _discard():
            if not cu.discard():
                def _notify():
                    msg = "%s: <i>%s</i>" % (
                        _("Cannot <b>discard</b> configuration file"),
                        cu.source(),)
                    self._notify_error(msg)
                GLib.idle_add(_notify)
            else:
                GLib.idle_add(self._remove_path, path)

        task = ParallelTask(_discard)
        task.name = "OnSourceDiscard"
        task.daemon = True
        task.start()

    def setup(self):
        """
        Setup the ConfigUpdatesViewController resources.
        """
        self._view.set_model(self._store)

        self._view.connect("source-edit", self._on_source_edit)
        self._view.connect("show-diff", self._on_show_diff)
        self._view.connect("source-merge", self._on_source_merge)
        self._view.connect("source-discard", self._on_source_discard)
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
        self.emit("view-cleared")

    def append(self, opaque):
        """
        Add a ConfigUpdate object to the store.
        """
        self._store.append([opaque])
        self.emit("view-filled")

    def append_many(self, opaque_list):
        """
        Append many ConfigUpdate objects to the store.
        """
        for opaque in opaque_list:
            self._store.append([opaque])
        self.emit("view-filled")

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
        self.set_many(config_updates)
        if self._nc is not None and self._avc is not None:
            with self._box_mutex:
                box = ConfigUpdatesNotificationBox(
                    self._entropy, self._avc, len(config_updates))
                self._box = box
                self._nc.append(box)
