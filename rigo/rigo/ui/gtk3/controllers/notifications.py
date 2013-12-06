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

from gi.repository import Gtk, GLib, GObject

from rigo.enums import LocalActivityStates
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    ConnectivityNotificationBox

from entropy.misc import ParallelTask
from entropy.i18n import _

class NotificationViewController(GObject.Object):

    """
    Base Class for NotificationBox Controller.
    """

    def __init__(self, notification_box):
        GObject.Object.__init__(self)
        self._box = notification_box
        self._context_id_map = {}

    def setup(self):
        """
        Controller Setup code
        """

    def append(self, box, timeout=None, context_id=None):
        """
        Append a notification to the Notification area.
        context_id is used to automatically drop any other
        notification exposing the same context identifier.
        """
        context_id = box.get_context_id()
        if context_id is not None:
            old_box = self._context_id_map.get(context_id)
            if old_box is not None:
                old_box.destroy()
            self._context_id_map[context_id] = box
        box.render()
        self._box.pack_start(box, False, False, 0)
        box.show()
        self._box.show()
        if timeout is not None:
            GLib.timeout_add_seconds(timeout, self.remove, box)

    def append_safe(self, box, timeout=None):
        """
        Thread-safe version of append().
        """
        def _append():
            self.append(box, timeout=timeout)
        GLib.idle_add(_append)

    def remove(self, box):
        """
        Remove a NotificationBox from this notification
        area, if there.
        """
        if box in self._box.get_children():
            context_id = box.get_context_id()
            if context_id is not None:
                self._context_id_map.pop(context_id, None)
            box.destroy()

    def remove_safe(self, box):
        """
        Thread-safe version of remove().
        """
        GLib.idle_add(self.remove, box)

    def clear(self, managed=True):
        """
        Clear all the notifications.
        """
        for child in self._box.get_children():
            if child.is_managed() and not managed:
                continue
            context_id = child.get_context_id()
            if context_id is not None:
                self._context_id_map.pop(context_id, None)
            child.destroy()

    def clear_safe(self, managed=True):
        """
        Thread-safe version of clear().
        """
        GLib.idle_add(self.clear, managed)


class UpperNotificationViewController(NotificationViewController):

    """
    Notification area widget controller.
    This class features the handling of some built-in
    Notification objects (like updates and outdated repositories)
    but also accepts external NotificationBox instances as well.
    """

    def __init__(self, entropy_client, entropy_ws,
                 notification_box):

        NotificationViewController.__init__(
            self, notification_box)

        self._entropy = entropy_client
        self._entropy_ws = entropy_ws

    def setup(self):
        """
        Reimplemented from NotificationViewController.
        """
        th = ParallelTask(self.__check_connectivity)
        th.daemon = True
        th.name = "CheckConnectivity"
        th.start()

    def __check_connectivity(self):
        """
        Execute connectivity check basing on Entropy
        Web Services availability.
        """
        with self._entropy.rwsem().reader():
            repositories = self._entropy.repositories()
            available = False
            for repository_id in repositories:
                if self._entropy_ws.get(repository_id) is not None:
                    available = True
                    break
            if not repositories:
                # no repos to check against
                available = True

            if not available:
                GLib.idle_add(self._notify_connectivity_issues)

    def _notify_connectivity_issues(self):
        """
        Cannot connect to Entropy Web Services.
        """
        box = ConnectivityNotificationBox()
        self.append(box)


class BottomNotificationViewController(NotificationViewController):

    """
    Bottom Notification Area.
    This area is only used to show Activity controls to User.
    For example, during repositories update, this area just
    shows one notification box stating that the above activity is in
    progress, making possible to switch to the Work View anytime.
    """

    UNIQUE_CONTEXT_ID = "BottomNotificationBoxContextId"

    __gsignals__ = {
        "show-work-view" : (GObject.SignalFlags.RUN_LAST,
                            None,
                            tuple(),
                            ),
        "show-queue-view" : (GObject.SignalFlags.RUN_LAST,
                             None,
                             tuple(),
                             ),
        "work-interrupt" : (GObject.SignalFlags.RUN_LAST,
                            None,
                            tuple(),
                            ),
    }

    def __init__(self, window, notification_box, preference_button):

        self._window = window
        NotificationViewController.__init__(
            self, notification_box)
        self._pref_button = preference_button

    def _on_work_view_show(self, widget):
        """
        User is asking to show the Work View.
        """
        self.emit("show-work-view")

    def _on_work_interrupt(self, widget):
        """
        User is asking to interrupt the Work.
        """
        self.emit("work-interrupt")

    def _on_show_activity(self, widget):
        """
        User is asking to show the Application Queue.
        """
        self.emit("show-queue-view")

    def _append_repositories_update(self):
        """
        Add a NotificationBox related to Repositories Update
        Activity in progress.
        """
        msg = _("Repositories Update in <b>progress</b>...")
        box = NotificationBox(
            msg, message_type=Gtk.MessageType.INFO,
            context_id=self.UNIQUE_CONTEXT_ID)
        box.add_button(_("Show me"), self._on_work_view_show)
        self.append(box)

    def _append_installing_apps(self):
        """
        Add a NotificationBox related to Applications Install
        Activity in progress.
        """
        msg = _("<b>Application Management</b> in progress...")
        box = NotificationBox(
            msg, message_type=Gtk.MessageType.INFO,
            context_id=self.UNIQUE_CONTEXT_ID)
        def _show_me(widget):
            self._on_work_view_show(widget)
            w, h = self._window.get_size()
            self._window.resize(w, 1)
        box.add_button(_("Show me"), _show_me)
        box.add_button(_("Activity"), self._on_show_activity)
        box.add_button(_("Interrupt"), self._on_work_interrupt)
        self.append(box)

    def _append_upgrading_system(self):
        """
        Add a NotificationBox related to System Upgrade
        Activity in progress.
        """
        msg = _("<b>System Upgrade</b> in progress...")
        box = NotificationBox(
            msg, message_type=Gtk.MessageType.INFO,
            context_id=self.UNIQUE_CONTEXT_ID)
        def _show_me(widget):
            self._on_work_view_show(widget)
            w, h = self._window.get_size()
            self._window.resize(w, 1)
        box.add_button(_("Show me"), _show_me)
        box.add_button(_("Activity"), self._on_show_activity)
        box.add_button(_("Interrupt"), self._on_work_interrupt)
        self.append(box)

    def set_activity(self, local_activity):
        """
        Set a current local Activity, showing the
        most appropriate NotificationBox.
        This method must be called from the MainLoop.
        """
        if local_activity == LocalActivityStates.READY:
            self.clear()
            self._pref_button.set_sensitive(True)
            return

        if local_activity == LocalActivityStates.UPDATING_REPOSITORIES:
            self._append_repositories_update()
            self._pref_button.set_sensitive(False)
            return
        elif local_activity == LocalActivityStates.MANAGING_APPLICATIONS:
            self._append_installing_apps()
            self._pref_button.set_sensitive(False)
            return
        elif local_activity == LocalActivityStates.UPGRADING_SYSTEM:
            self._append_upgrading_system()
            self._pref_button.set_sensitive(False)
            return

        raise NotImplementedError()
