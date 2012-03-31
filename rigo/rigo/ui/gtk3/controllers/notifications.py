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
    RepositoriesUpdateNotificationBox, UpdatesNotificationBox, \
    ConnectivityNotificationBox

from entropy.client.interfaces.repository import Repository
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

    def __init__(self, activity_rwsem, entropy_client, entropy_ws,
                 rigo_service, avc, notification_box):

        NotificationViewController.__init__(
            self, notification_box)

        self._avc = avc
        self._service = rigo_service
        self._activity_rwsem = activity_rwsem
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._updates = None
        self._security_updates = None

    def setup(self):
        """
        Reimplemented from NotificationViewController.
        """
        GLib.timeout_add_seconds(1, self._calculate_updates)
        GLib.idle_add(self._check_connectivity)

    def _check_connectivity(self):
        th = ParallelTask(self.__check_connectivity)
        th.daemon = True
        th.name = "CheckConnectivity"
        th.start()

    def _calculate_updates(self):
        th = ParallelTask(self.__calculate_updates)
        th.daemon = True
        th.name = "CalculateUpdates"
        th.start()

    def __check_connectivity(self):
        """
        Execute connectivity check basing on Entropy
        Web Services availability.
        """
        self._entropy.rwsem().reader_acquire()
        try:
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
        finally:
            self._entropy.rwsem().reader_release()

    def __order_updates(self, updates):
        """
        Order updates using PN.
        """
        def _key_func(x):
            return self._entropy.open_repository(
                x[1]).retrieveName(x[0]).lower()
        return sorted(updates, key=_key_func)

    def __calculate_updates(self):
        #self._activity_rwsem.reader_acquire()
        self._entropy.rwsem().reader_acquire()
        try:
            unavailable_repositories = \
                self._entropy.unavailable_repositories()
            if unavailable_repositories:
                GLib.idle_add(self._notify_unavailable_repositories_safe,
                              unavailable_repositories)
                return
            if Repository.are_repositories_old():
                GLib.idle_add(self._notify_old_repositories_safe)
                return

            updates, removal, fine, spm_fine = \
                self._entropy.calculate_updates()
            self._updates = self.__order_updates(updates)
            self._security_updates = self._entropy.calculate_security_updates()
        finally:
            self._entropy.rwsem().reader_release()
            #self._activity_rwsem.reader_release()

        GLib.idle_add(self._notify_updates_safe)

    def _notify_connectivity_issues(self):
        """
        Cannot connect to Entropy Web Services.
        """
        box = ConnectivityNotificationBox()
        self.append(box)

    def _notify_updates_safe(self):
        """
        Add NotificationBox signaling the user that updates
        are available.
        """
        updates_len = len(self._updates)
        if updates_len == 0:
            # no updates, do not show anything
            return

        box = UpdatesNotificationBox(
            self._entropy, self._avc,
            updates_len, len(self._security_updates))
        box.connect("upgrade-request", self._on_upgrade)
        box.connect("show-request", self._on_update_show)
        self.append(box)

    def _notify_old_repositories_safe(self):
        """
        Add a NotificationBox signaling the User that repositories
        are old..
        """
        box = RepositoriesUpdateNotificationBox(
            self._entropy, self._avc)
        box.connect("update-request", self._on_update)
        self.append(box)

    def _notify_unavailable_repositories_safe(self, unavailable):
        """
        Add a NotificationBox signaling the User that some repositories
        are unavailable..
        """
        box = RepositoriesUpdateNotificationBox(
            self._entropy, self._avc, unavailable=unavailable)
        box.connect("update-request", self._on_update)
        self.append(box)

    def _on_upgrade(self, box):
        """
        Callback requesting Packages Update.
        """
        self.remove(box)
        self._service.upgrade_system()

    def _on_update(self, box):
        """
        Callback requesting Repositories Update.
        """
        self.remove(box)
        self._service.update_repositories([], True)

    def _on_update_show(self, *args):
        """
        Callback from UpdatesNotification "Show" button.
        Showing updates.
        """
        self._avc.set_many_safe(self._updates)

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
    }

    def __init__(self, notification_box):

        NotificationViewController.__init__(
            self, notification_box)

    def _on_work_view_show(self, widget):
        """
        User is asking to show the Work View.
        """
        self.emit("show-work-view")

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
        box.add_button(_("Show me"), self._on_work_view_show)
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
        box.add_button(_("Show me"), self._on_work_view_show)
        self.append(box)

    def set_activity(self, local_activity):
        """
        Set a current local Activity, showing the
        most appropriate NotificationBox.
        This method must be called from the MainLoop.
        """
        if local_activity == LocalActivityStates.READY:
            self.clear()
            return

        if local_activity == LocalActivityStates.UPDATING_REPOSITORIES:
            self._append_repositories_update()
            return
        elif local_activity == LocalActivityStates.MANAGING_APPLICATIONS:
            self._append_installing_apps()
            return
        elif local_activity == LocalActivityStates.UPGRADING_SYSTEM:
            self._append_upgrading_system()
            return

        raise NotImplementedError()
