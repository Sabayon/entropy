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
from rigo.models.repository import Repository
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    RenameRepositoryNotificationBox
from rigo.models.preference import Preference

from entropy.const import const_debug_write
from entropy.misc import ParallelTask


class RepositoryViewController(GObject.Object):

    def __init__(self, prefc, rigo_service, repo_store, repo_view):
        GObject.Object.__init__(self)
        self._prefc = prefc
        self._service = rigo_service
        self._store = repo_store
        self._view = repo_view
        self._nc = None
        self._avc = None

    def load(self):
        """
        Request a content (re)load.
        """
        const_debug_write(
            __name__, "RepoVC: load() called")
        def _load():
            repositories = self._service.list_repositories()
            objs = []
            for repository_id, description, enabled in repositories:
                obj = Repository(repository_id, description, enabled)
                objs.append(obj)
            self.set_many_safe(objs)

        task = ParallelTask(_load)
        task.name = "OnRepositoryLoadRequest"
        task.daemon = True
        task.start()

    def _on_repository_toggle(self, widget, path, repo):
        """
        Enable/Disable Repository event from View
        """
        enabled = repo.enabled()
        repository = repo.repository()

        if enabled:
            outcome = self._service.disable_repository(repository)
        else:
            outcome = self._service.enable_repository(repository)
        if not outcome and self._nc is not None:
            if enabled:
                msg = _("Cannot disable <b>%s</b>. Sorry!")
            else:
                msg = _("Cannot enable <b>%s</b>. Sorry!")

            box = NotificationBox(
                prepare_markup(msg % (repository,)),
                message_type=Gtk.MessageType.WARNING,
                context_id=self._service.REPOSITORY_SETTINGS_CONTEXT_ID)
            box.add_destroy_button(_("_Ok"))
            self._nc.append(box)

    def _on_repository_rename(self, widget, path, repo):
        """
        Rename Repository event from View
        """
        if self._nc is not None:
            box = RenameRepositoryNotificationBox(
                repo, self._service)
            self._nc.append(box)

    def _on_settings_changed(self, service):
        """
        RigoServiceController is telling us that Repository Settings have
        successfully changed.
        """
        self.clear()
        self.load()

    def _show(self):
        """
        Show Repository Management interface, if possible.
        """
        if self._avc is not None:
            GLib.idle_add(self._avc.emit, "view-want-change",
                          RigoViewStates.REPOSITORY_VIEW_STATE,
                          None)

    def setup(self):
        """
        Setup the RepositoryViewController resources.
        """
        self._view.set_model(self._store)
        self._service.connect("repositories-settings-changed",
                              self._on_settings_changed)
        self._view.connect("toggle-repo", self._on_repository_toggle)
        self._view.connect("rename-repo", self._on_repository_rename)

        pref = Preference(
            50,
            _("Manage Repositories"),
            _("Enable, disable or rename Repositories."),
            Icons.REPOSITORY, self._show)
        self._prefc.append(pref)

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
