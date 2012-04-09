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
import errno
import copy
import dbus
from threading import Lock, Semaphore, Timer

from gi.repository import Gtk, GLib, GObject

from rigo.paths import CONF_DIR
from rigo.enums import RigoViewStates, AppActions
from rigo.models.application import Application, ApplicationMetadata
from rigo.utils import escape_markup, prepare_markup
from rigo.ui.gtk3.widgets.notifications import \
    NotificationBox

from entropy.cache import EntropyCacher
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
                          (GObject.TYPE_PYOBJECT,
                           GObject.TYPE_PYOBJECT,),
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

    RECENT_SEARCHES_DIR = os.path.join(CONF_DIR, "recent_searches")
    RECENT_SEARCHES_CACHE_KEY = "list"
    RECENT_SEARCHES_MAX_LEN = 20
    MIN_RECENT_SEARCH_KEY_LEN = 2

    def __init__(self, activity_rwsem, entropy_client, entropy_ws,
                 rigo_service, icons, nf_box,
                 search_entry, search_entry_completion,
                 search_entry_store, store, view):
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
        self._nc = None

        self._cacher = EntropyCacher()
        self._search_thread_mutex = Lock()

        self._search_completion = search_entry_completion
        self._search_completion_model = search_entry_store
        self._search_writeback_mutex = Lock()
        self._search_writeback_thread = None

    def set_notification_controller(self, nc):
        """
        Bind a NotificationViewController to this object.
        """
        self._nc = nc

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

    def _search(self, old_text, _force=False):
        cur_text = self._search_entry.get_text()
        if (cur_text == old_text and cur_text) or _force:
            search_text = copy.copy(old_text)
            search_text = const_convert_to_unicode(
                search_text, enctype=etpConst['conf_encoding'])
            if _force:
                self._search_entry.set_text(search_text)
            th = ParallelTask(self.__search_thread, search_text)
            th.name = "SearchThread"
            th.start()

    def __search_produce_matches(self, text):
        """
        Execute the actual search inside Entropy repositories.
        """
        def _prepare_for_search(txt):
            return txt.replace(" ", "-").lower()

        self._entropy.rwsem().reader_acquire()
        try:
            matches = []
            # package set search
            if text.startswith(etpConst['packagesetprefix']):
                sets = self._entropy.Sets()
                package_deps = sets.expand(text)
                for package_dep in package_deps:
                    pkg_id, pkg_repo = self._entropy.atom_match(
                        package_dep)
                    if pkg_id != -1:
                        matches.append((pkg_id, pkg_repo))

            if not matches:
                # exact match
                pkg_matches, rc = self._entropy.atom_match(
                    text, multi_match=True,
                    multi_repo=True, mask_filter=False)
                matches.extend(pkg_matches)

                # atom searching (name and desc)
                search_matches = self._entropy.atom_search(
                    text,
                    repositories = self._entropy.repositories(),
                    description = True)

                matches.extend([x for x in search_matches \
                                    if x not in matches])

                if not search_matches:
                    search_matches = self._entropy.atom_search(
                        _prepare_for_search(text),
                        repositories = self._entropy.repositories())
                    matches.extend(
                        [x for x in search_matches if x not in matches])

            return matches
        finally:
            self._entropy.rwsem().reader_release()

    def install(self, dependency, simulate=False):
        """
        Try to match dependency to an Application and then install
        it, if possible.
        """
        const_debug_write(
            __name__,
            "install: %s" % (dependency,))
        self._entropy.rwsem().reader_acquire()
        try:
            pkg_match = self._entropy.atom_match(dependency)
        finally:
            self._entropy.rwsem().reader_release()

        pkg_id, pkg_repo = pkg_match
        if pkg_id == -1:
            const_debug_write(
                __name__,
                "install: "
                "no match for: %s" % (dependency,))
            def _notify():
                msg = _("Application <b>%s</b> not found")
                msg = msg % (dependency,)
                box = NotificationBox(
                    prepare_markup(msg), Gtk.MessageType.ERROR,
                    context_id="AppInstallNotFoundContextId")
                self._nc.append(box, timeout=10)
            if self._nc is not None:
                GLib.idle_add(_notify)
            return

        app = Application(
            self._entropy, self._entropy_ws,
            pkg_match)
        self._service.application_request(
            app, AppActions.INSTALL, simulate=simulate)

        const_debug_write(
            __name__,
            "install: "
            "application_request() sent for: %s, %s" % (
                dependency, app,))

    def install_package(self, package_path, simulate=False):
        """
        Install Entropy Package file.
        """
        const_debug_write(
            __name__,
            "install_package: %s" % (package_path,))

        self._service.package_install_request(
            package_path, simulate=simulate)

        const_debug_write(
            __name__,
            "install_package: "
            "package_install_request() sent for: %s" % (
                package_path,))

    def remove(self, dependency, simulate=False):
        """
        Try to match dependency to an Application and then remove
        it, if possible.
        """
        const_debug_write(
            __name__,
            "remove: %s" % (dependency,))
        self._entropy.rwsem().reader_acquire()
        try:
            inst_repo = self._entropy.installed_repository()
            pkg_repo = inst_repo.repository_id()
            pkg_id, rc = inst_repo.atomMatch(dependency)
        finally:
            self._entropy.rwsem().reader_release()

        if pkg_id == -1:
            const_debug_write(
                __name__,
                "remove: "
                "no match for: %s" % (dependency,))
            def _notify():
                msg = _("Application <b>%s</b> not found")
                msg = msg % (dependency,)
                box = NotificationBox(
                    prepare_markup(msg), Gtk.MessageType.ERROR,
                    context_id="AppRemoveNotFoundContextId")
                self._nc.append(box, timeout=10)
            if self._nc is not None:
                GLib.idle_add(_notify)
            return

        app = Application(
            self._entropy, self._entropy_ws,
            (pkg_id, pkg_repo))
        self._service.application_request(
            app, AppActions.REMOVE, simulate=simulate)

        const_debug_write(
            __name__,
            "remove: "
            "application_request() sent for: %s, %s" % (
                dependency, app,))

    def upgrade(self, simulate=False):
        """
        Launch a System Upgrade activity.
        """
        const_debug_write(
            __name__, "upgrade")
        self._service.upgrade_system(simulate=simulate)
        const_debug_write(
            __name__, "upgrade:"
            " upgrade_system() sent")

    def __simulate_orphaned_apps(self, text):

        const_debug_write(
            __name__,
            "__simulate_orphaned_apps: "
            "%s" % (text,))
        self._entropy.rwsem().reader_acquire()
        try:
            inst_repo = self._entropy.installed_repository()
            pkg_ids = inst_repo.searchPackages(text, just_id=True)
            manual_pkg_ids, rc = inst_repo.atomMatch(text, multiMatch=True)
        finally:
            self._entropy.rwsem().reader_release()

        def _notify():
            self._service._unsupported_applications_signal(
                list(manual_pkg_ids), pkg_ids)
        GLib.idle_add(_notify)

        const_debug_write(
            __name__,
            "__simulate_orphaned_apps: completed")

    def __search_thread(self, text):

        ## special keywords hook
        if text == "rigo:update":
            self._update_repositories_safe()
            return
        if text == "rigo:upgrade":
            self.upgrade()
            return
        elif text == "rigo:confupdate":
            self._service.configuration_updates()
            return

        # debug, simulation
        elif text == "rigo:vte":
            GLib.idle_add(self.emit, "view-want-change",
                          RigoViewStates.WORK_VIEW_STATE,
                          None)
            return
        elif text.startswith("rigo:simulate:i:"):
            sim_str = text[len("rigo:simulate:i:"):].strip()
            if sim_str:
                self.install(sim_str, simulate=True)
                return
        elif text.startswith("rigo:simulate:r:"):
            sim_str = text[len("rigo:simulate:r:"):].strip()
            if sim_str:
                self.remove(sim_str, simulate=True)
                return
        elif text.startswith("rigo:simulate:o:"):
            sim_str = text[len("rigo:simulate:o:"):].strip()
            if sim_str:
                self.__simulate_orphaned_apps(sim_str)
                return
        if text == "rigo:simulate:u":
            self.upgrade(simulate=True)
            return

        # serialize searches to avoid segfaults with sqlite3
        # (apparently?)
        with self._search_thread_mutex:
            # Do not execute search if repositories are
            # being hold by other write
            acquired = self._service.repositories_lock.acquire(False)
            if not acquired:
                # this avoids having starvation here.
                return
            try:

               matches = self.__search_produce_matches(text)
               # we have to decide if to show the treeview in
               # the UI thread, to avoid races (and also because we
               # have to...)
               self.set_many_safe(matches, _from_search=text)
               if matches:
                   self._add_recent_search_safe(text)

            finally:
                self._service.repositories_lock.release()

    def _setup_search_view(self, items_count, text):
        """
        Setup UI in order to show a "not found" message if required.
        """
        nf_box = self._not_found_box
        if items_count or text is None:
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
        self._entropy.rwsem().reader_acquire()
        try:
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
        finally:
            self._entropy.rwsem().reader_release()

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

    def _ensure_cache_dir(self):
        """
        Make sure the cache directory is available.
        """
        path = self.RECENT_SEARCHES_DIR
        try:
            os.makedirs(path)
        except OSError as err:
            if err.errno == errno.EEXIST:
                if os.path.isfile(path):
                    os.remove(path) # fail, yeah
                return
            elif err.errno == errno.ENOTDIR:
                # wtf? we will fail later for sure
                return
            elif err.errno == errno.EPERM:
                # meh!
                return
            raise

    def _load_recent_searches(self):
        """
        Load from disk a list() of recent searches.
        """
        self._ensure_cache_dir()
        data = self._cacher.pop(
            self.RECENT_SEARCHES_CACHE_KEY,
            cache_dir=self.RECENT_SEARCHES_DIR)
        if data is None:
            return []
        return data[:self.RECENT_SEARCHES_MAX_LEN]

    def _store_recent_searches(self, searches):
        """
        Store to disk a list of recent searches.
        """
        self._ensure_cache_dir()
        self._cacher.save(
            self.RECENT_SEARCHES_CACHE_KEY,
            searches,
            cache_dir=self.RECENT_SEARCHES_DIR)

    def _store_searches_thread(self):
        """
        Thread body doing recent searches writeback.
        """
        data = {
            'sem': Semaphore(0),
            'res': None,
        }
        const_debug_write(
            __name__, "running recent searches writeback")

        def _get_list():
            searches = [x[0] for x in self._search_completion_model]
            data['res'] = searches
            data['sem'].release()
        GLib.idle_add(_get_list)

        data['sem'].acquire()
        searches = data['res']
        self._store_recent_searches(searches)
        self._search_writeback_thread = None
        const_debug_write(
            __name__, "searches writeback complete")

    def _add_recent_search_safe(self, search):
        """
        Add text element to recent searches.
        """
        if len(search) < self.MIN_RECENT_SEARCH_KEY_LEN:
            return

        def _prepend():
            self._search_completion_model.prepend((search,))
        GLib.idle_add(_prepend)

        with self._search_writeback_mutex:
            if self._search_writeback_thread is None:
                task = Timer(15.0, self._store_searches_thread)
                task.name = "StoreRecentSearches"
                task.daemon = True
                self._search_writeback_thread = task
                task.start()

    def search(self, text):
        """
        Execute an Application Search.
        """
        self._search(text, _force=True)

    def setup(self):
        # load recent searches
        for search in self._load_recent_searches():
            self._search_completion_model.append([search])

        # not enabling because it causes SIGFPE (Gtk3 bug?)
        # self._search_entry.set_completion(self._search_completion)

        self._view.set_model(self._store)
        self._search_entry.connect(
            "changed", self._search_changed)
        self._search_entry.connect("icon-release",
            self._search_icon_release)
        self._view.show()

    def clear(self):
        self._view.clear_model()
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
        self._view.clear_model()
        ApplicationMetadata.discard()
        self.append_many(opaque_list)
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
