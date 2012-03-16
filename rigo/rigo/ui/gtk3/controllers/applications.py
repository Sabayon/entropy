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

import copy
import dbus

from gi.repository import Gtk, GLib, GObject

from rigo.enums import RigoViewStates
from rigo.models.application import Application, ApplicationMetadata
from rigo.utils import escape_markup, prepare_markup

from entropy.const import etpConst, const_debug_write, \
    const_debug_enabled, const_convert_to_unicode
from entropy.misc import ParallelTask
from entropy.i18n import _


class ApplicationsViewController(GObject.Object):

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
        # View has been filled
        "view-want-change" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          (GObject.TYPE_PYOBJECT,),
                          ),
        # User logged in to Entropy Web Services
        "logged-in"  : (GObject.SignalFlags.RUN_LAST,
                        None,
                        (GObject.TYPE_PYOBJECT,),
                        ),
        # User logged out from Entropy Web Services
        "logged-out"  : (GObject.SignalFlags.RUN_LAST,
                         None,
                         tuple(),
                         ),
    }

    def __init__(self, activity_rwsem, entropy_client, entropy_ws,
                 rigo_service, icons, nf_box,
                 search_entry, store, view):
        GObject.Object.__init__(self)
        self._activity_rwsem = activity_rwsem
        self._entropy = entropy_client
        self._service = rigo_service
        self._icons = icons
        self._entropy_ws = entropy_ws
        self._search_entry = search_entry
        self._store = store
        self._view = view
        self._nf_box = nf_box
        self._not_found_search_box = None
        self._not_found_label = None

    def _search_icon_release(self, search_entry, icon_pos, _other):
        """
        Event associated to the Search bar icon click.
        Here we catch secondary icon click to reset the search entry text.
        """
        if search_entry is not self._search_entry:
            return
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            search_entry.set_text("")
            self.clear()
            search_entry.emit("changed")
        elif self._store.get_iter_first():
            # primary icon click will force UI to switch to Browser mode
            self.emit("view-filled")

    def _search_changed(self, search_entry):
        GLib.timeout_add(700, self._search, search_entry.get_text())

    def _search(self, old_text):
        cur_text = self._search_entry.get_text()
        if cur_text == old_text and cur_text:
            search_text = copy.copy(old_text)
            search_text = const_convert_to_unicode(
                search_text, enctype=etpConst['conf_encoding'])
            th = ParallelTask(self.__search_thread, search_text)
            th.name = "SearchThread"
            th.start()

    def __search_thread(self, text):
        def _prepare_for_search(txt):
            return txt.replace(" ", "-").lower()

        ## special keywords hook
        if text == "rigo:update":
            self._update_repositories_safe()
            return
        if text == "rigo:vte":
            GLib.idle_add(self.emit, "view-want-change",
                          RigoViewStates.WORK_VIEW_STATE)
            return
        if text == "rigo:output":
            GLib.idle_add(self.emit, "view-want-change",
                          RigoViewStates.WORK_VIEW_STATE)
            GLib.idle_add(self._service.output_test)
            return

        # Do not execute search if repositories are
        # being hold by other write
        self._activity_rwsem.reader_acquire()
        try:

            matches = []

            # exact match
            pkg_matches, rc = self._entropy.atom_match(
                text, multi_match = True,
                multi_repo = True, mask_filter = False)
            matches.extend(pkg_matches)

            # atom searching (name and desc)
            search_matches = self._entropy.atom_search(
                text,
                repositories = self._entropy.repositories(),
                description = True)

            matches.extend([x for x in search_matches if x not in matches])

            if not search_matches:
                search_matches = self._entropy.atom_search(
                    _prepare_for_search(text),
                    repositories = self._entropy.repositories())
                matches.extend([x for x in search_matches if x not in matches])

            # we have to decide if to show the treeview in
            # the UI thread, to avoid races (and also because we
            # have to...)
            self.set_many_safe(matches, _from_search=text)

        finally:
            self._activity_rwsem.reader_release()

    def _setup_search_view(self, items_count, text):
        """
        Setup UI in order to show a "not found" message if required.
        """
        nf_box = self._not_found_box
        if items_count:
            nf_box.set_property("expand", False)
            nf_box.hide()
            self._view.get_parent().show()
        else:
            self._view.get_parent().hide()
            self._setup_not_found_box(text)
            nf_box.set_property("expand", True)
            nf_box.show()

    def _setup_not_found_box(self, search_text):
        """
        Setup "not found" message label and layout
        """
        nf_box = self._not_found_box
        # now self._not_found_label is available
        meant_packages = self._entropy.get_meant_packages(
            search_text)
        text = escape_markup(search_text)

        msg = "%s <b>%s</b>" % (
            escape_markup(_("Nothing found for")),
            text,)
        if meant_packages:
            first_entry = meant_packages[0]
            app = Application(
                self._entropy, self._entropy_ws,
                first_entry)
            name = app.name

            msg += ", %s" % (
                prepare_markup(_("did you mean <a href=\"%s\">%s</a>?")) % (
                    escape_markup(name),
                    escape_markup(name),),)

        self._not_found_label.set_markup(msg)

    def _on_not_found_label_activate_link(self, label, text):
        """
        Handling the click event on <a href=""/> of the
        "not found" search label. Just write the coming text
        to the Gtk.SearchEntry object.
        """
        if text:
            self._search_entry.set_text(text)
            self._search(text)

    @property
    def _not_found_box(self):
        """
        Return a Gtk.VBox containing the view that should
        be shown when no apps have been found (due to a search).
        """
        if self._not_found_search_box is not None:
            return self._not_found_search_box
        # here we always have to access from the same thread
        # otherwise Gtk will go boom anyway
        box_align = Gtk.Alignment()
        box_align.set_padding(10, 10, 0, 0)
        box = Gtk.VBox()
        box_align.add(box)
        label = Gtk.Label(_("Not found"))
        label.connect("activate-link", self._on_not_found_label_activate_link)
        box.pack_start(label, True, True, 0)
        box_align.show()

        self._nf_box.pack_start(box_align, False, False, 0)
        self._nf_box.show_all()
        self._not_found_label = label
        self._not_found_search_box = box_align
        return box_align

    def _update_repositories(self):
        """
        Spawn Repository Update on RigoDaemon
        """
        self._service.update_repositories([], True)

    def _update_repositories_safe(self):
        """
        Same as _update_repositories() but thread safe.
        """
        GLib.idle_add(self._update_repositories)

    def setup(self):
        self._view.set_model(self._store)
        self._search_entry.connect(
            "changed", self._search_changed)
        self._search_entry.connect("icon-release",
            self._search_icon_release)
        self._view.show()

    def clear(self):
        self._store.clear()
        ApplicationMetadata.discard()
        if const_debug_enabled():
            const_debug_write(__name__, "AVC: emitting view-cleared")
        self.emit("view-cleared")

    def append(self, opaque):
        self._store.append([opaque])
        if const_debug_enabled():
            const_debug_write(__name__, "AVC: emitting view-filled")
        self.emit("view-filled")

    def append_many(self, opaque_list):
        for opaque in opaque_list:
            self._store.append([opaque])
        if const_debug_enabled():
            const_debug_write(__name__, "AVC: emitting view-filled")
        self.emit("view-filled")

    def set_many(self, opaque_list, _from_search=None):
        self._store.clear()
        ApplicationMetadata.discard()
        self.append_many(opaque_list)
        if _from_search:
            self._setup_search_view(
                len(opaque_list), _from_search)

    def clear_safe(self):
        GLib.idle_add(self.clear)

    def append_safe(self, opaque):
        GLib.idle_add(self.append, opaque)

    def append_many_safe(self, opaque_list):
        GLib.idle_add(self.append_many, opaque_list)

    def set_many_safe(self, opaque_list, _from_search=None):
        GLib.idle_add(self.set_many, opaque_list,
                      _from_search)
