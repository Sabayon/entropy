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
import sys
import copy
import tempfile
import time
from threading import Lock

import dbus

sys.path.insert(0, "../lib")
sys.path.insert(1, "../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/lib")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/rigo")
sys.path.insert(6, "/usr/lib/rigo")


from gi.repository import Gtk, Gdk, Gio, GLib, GObject, Vte, Pango

from rigo.paths import DATA_DIR
from rigo.enums import Icons, AppActions
from rigo.entropyapi import EntropyWebService
from rigo.models.application import Application, ApplicationMetadata
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    RepositoriesUpdateNotificationBox, UpdatesNotificationBox, \
    LoginNotificationBox, ConnectivityNotificationBox
from rigo.ui.gtk3.widgets.welcome import WelcomeBox
from rigo.ui.gtk3.widgets.stars import ReactiveStar
from rigo.ui.gtk3.widgets.comments import CommentBox
from rigo.ui.gtk3.widgets.terminal import TerminalWidget
from rigo.ui.gtk3.widgets.images import ImageBox
from rigo.ui.gtk3.models.appliststore import AppListStore
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme
from rigo.utils import build_application_store_url, build_register_url, \
    escape_markup, prepare_markup

from RigoDaemon.enums import ActivityStates

from entropy.const import etpConst, etpUi, const_debug_write, \
    const_debug_enabled, const_convert_to_unicode, const_isunicode
from entropy.client.interfaces import Client
from entropy.client.interfaces.repository import Repository
from entropy.services.client import WebService
from entropy.misc import TimeScheduled, ParallelTask, ReadersWritersSemaphore
from entropy.i18n import _, ngettext
from entropy.output import darkgreen, brown, darkred, red, blue

import entropy.tools

class RigoServiceController(GObject.Object):

    """
    This is the Rigo Application frontend to Rigo Daemon.
    Handles privileged requests on our behalf.
    """

    __gsignals__ = {
        # we request to lock the whole UI wrt repo
        # interaction
        "repositories-updating" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                   ),
        # View has been filled
        "repositories-updated" : (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  tuple(),
                                  ),
    }

    DBUS_INTERFACE = "org.sabayon.Rigo"
    DBUS_PATH = "/daemon"
    _OUTPUT_SIGNAL = "output"
    _REPOSITORIES_UPDATED_SIGNAL = "repositories_updated"
    _TRANSFER_OUTPUT_SIGNAL = "transfer_output"

    def __init__(self, rigo_app, activity_rwsem, entropy_client, entropy_ws):
        GObject.Object.__init__(self)
        self._rigo = rigo_app
        self._activity_rwsem = activity_rwsem
        self._nc = None
        self._wc = None
        self._avc = None
        self._terminal = None
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self.__dbus_main_loop = None
        self.__system_bus = None
        self.__entropy_bus = None
        self.__entropy_bus_mutex = Lock()
        self._connected_mutex = Lock()
        self._connected = False
        self._registered_signals = {}
        self._registered_signals_mutex = Lock()

    def set_applications_controller(self, avc):
        """
        Bind ApplicationsViewController object to this class.
        """
        self._avc = avc

    def set_terminal(self, terminal):
        """
        Bind a TerminalWidget to this object, in order to be used with
        events coming from dbus.
        """
        self._terminal = terminal

    def set_work_controller(self, wc):
        """
        Bind a WorkViewController to this object in order to be used to
        set progress status.
        """
        self._wc = wc

    def set_notification_controller(self, nc):
        """
        Bind a NotificationViewController to this object.
        """
        self._nc = nc

    @property
    def _dbus_main_loop(self):
        if self.__dbus_main_loop is None:
            from dbus.mainloop.glib import DBusGMainLoop
            self.__dbus_main_loop = DBusGMainLoop(set_as_default=True)
        return self.__dbus_main_loop

    @property
    def _system_bus(self):
        if self.__system_bus is None:
            self.__system_bus = dbus.SystemBus(
                mainloop=self._dbus_main_loop)
        return self.__system_bus

    @property
    def _entropy_bus(self):
        with self.__entropy_bus_mutex:
            if self.__entropy_bus is None:
                self.__entropy_bus = self._system_bus.get_object(
                    self.DBUS_INTERFACE, self.DBUS_PATH
                    )

                self.__entropy_bus.connect_to_signal(
                    self._OUTPUT_SIGNAL, self._output_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                self.__entropy_bus.connect_to_signal(
                    self._TRANSFER_OUTPUT_SIGNAL,
                    self._transfer_output_signal,
                    dbus_interface=self.DBUS_INTERFACE)

            return self.__entropy_bus

    def _repositories_updated_signal(self, request_id, result, message):
        """
        Signal coming from RigoDaemon notifying us that repositories have
        been updated.
        """
        with self._registered_signals_mutex:
            our_signals = self._registered_signals.get(
                self._REPOSITORIES_UPDATED_SIGNAL)
            if our_signals is None:
                # not generated by us
                return
            if our_signals:
                sig_match = our_signals.pop(0)
                sig_match.remove()

        self._release_local_resources()
        # 1 -- ACTIVITY CRIT :: OFF
        self._activity_rwsem.writer_release()

        self.emit("repositories-updated")
        if const_debug_enabled():
            const_debug_write(__name__, "RigoServiceController: unlock-ui")

    def _output_signal(self, text, header, footer, back, importance, level,
               count_c, count_t, percent):
        """
        Entropy Client output() method from RigoDaemon comes here.
        Will be redirected to a virtual terminal here in Rigo.
        This is called in the Gtk.MainLoop.
        """
        if count_c == 0 and count_t == 0:
            count = None
        else:
            count = (count_c, count_t)

        if self._terminal is None:
            self._entropy.output(text, header=header, footer=footer,
                                 back=back, importance=importance,
                                 level=level, count=count,
                                 percent=percent)
            return

        color_func = darkgreen
        if level == "warning":
            color_func = brown
        elif level == "error":
            color_func = darkred

        count_str = ""
        if count:
            if len(count) > 1:
                if percent:
                    fraction = float(count[0])/count[1]
                    percent_str = str(round(fraction*100, 1))
                    count_str = " ("+percent_str+"%) "
                else:
                    count_str = " (%s/%s) " % (red(str(count[0])),
                        blue(str(count[1])),)

        # reset cursor
        self._terminal.feed_child(chr(27) + '[2K')
        if back:
            msg = "\r" + color_func(">>") + " " + header + count_str + text \
                + footer
        else:
            msg = "\r" + color_func(">>") + " " + header + count_str + text \
                + footer + "\r\n"

        self._terminal.feed_child(msg)

    def _transfer_output_signal(self, average, downloaded_size, total_size,
                                data_transfer_bytes, time_remaining_secs):
        """
        Entropy UrlFetchers update() method (via transfer_output()) from
        RigoDaemon comes here. Will be redirected to WorkAreaController
        Progress Bar if available.
        """
        if self._wc is None:
            return

        fraction = float(average) / 100

        human_dt = entropy.tools.bytes_into_human(data_transfer_bytes)

        text = "%s/%s kB @ %s/sec, %s" % (
                    round(float(downloaded_size)/1024, 1),
                    round(total_size, 1),
                    human_dt, time_remaining_secs)

        self._wc.set_progress(fraction, text=text)

    def activity(self):
        """
        Return RigoDaemon activity states (any of RigoDaemon.ActivityStates
        values).
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).activity()

    def output_test(self):
        """
        Test Output Signaling. Will be removed in future Rigo versions.
        """
        if self._wc is not None:
            self._wc.activate_progress_bar()
            self._wc.activate_app_box()
        dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).output_test()

    def output_test_safe(self):
        """
        Same as output_test() but thread-safe.
        """
        GLib.idle_add(self.output_test)

    def _connect(self):
        """
        Inform RigoDaemon that a new Client is now connected.
        This MUST be called after Entropy Resources Lock is
        acquired in exclusive mode.
        """
        with self._connected_mutex:
            if self._connected:
                return
            # inform daemon that a new instance is now connected
            dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).connect()
            self._connected = True

    def _release_local_resources(self):
        """
        Release all the local resources (like repositories)
        that shall be used by RigoDaemon.
        For example, leaving EntropyRepository objects open
        would cause sqlite3 to deadlock.
        """
        self._avc.clear_safe()
        self._entropy.close_repositories()

    def _scale_up(self):
        """
        Acquire (in blocking mode) the Entropy Resources Lock
        in exclusive mode. Scale up privileges, and ask for
        root password if not done yet.
        """
        # FIXME, complete, need to be nice and not block, etc
        # FIXME, ask for password.
        self._entropy.promote_resources(blocking=True)
        self._connect()
        return True

    def _update_repositories(self, repositories, force):
        """
        Ask RigoDaemon to update repositories once we're
        100% sure that the UI is locked down.
        """
        while not self._rigo.is_ui_locked():
            if const_debug_enabled():
                const_debug_write(__name__, "RigoServiceController: "
                                  "waiting Rigo UI lock")
            time.sleep(0.5)

        if const_debug_enabled():
            const_debug_write(__name__, "RigoServiceController: "
                              "rigo UI now locked!")

        # 1 -- ACTIVITY CRIT :: ON
        self._activity_rwsem.writer_acquire()

        # connect our signal
        sig_match = self._entropy_bus.connect_to_signal(
            self._REPOSITORIES_UPDATED_SIGNAL,
            self._repositories_updated_signal,
            dbus_interface=self.DBUS_INTERFACE)

        with self._registered_signals_mutex:
            # and register it as a signal generated by us
            obj = self._registered_signals.setdefault(
                self._REPOSITORIES_UPDATED_SIGNAL, [])
            obj.append(sig_match)

        # Clear all the NotificationBoxes from upper area
        # we don't want people to click on them during the
        # the repo update. Kill the completely.
        if self._nc is not None:
            self._nc.clear_safe()

        self._terminal.reset()
        self._release_local_resources()
        iface = dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE)
        iface.update_repositories(repositories, 1, force)

    def update_repositories(self, repositories, force):
        """
        Local method used to start Entropy repositories
        update.
        """
        if not self._scale_up():
            return

        if self._wc is not None:
            self._wc.activate_progress_bar()
            self._wc.deactivate_app_box()

        self.emit("repositories-updating", Rigo.WORK_VIEW_STATE)
        if const_debug_enabled():
            const_debug_write(__name__, "RigoServiceController: "
                              "repositories-updating")

        task = ParallelTask(self._update_repositories,
                            repositories, force)
        task.name = "UpdateRepositoriesThread"
        task.daemon = True
        task.start()


class WorkViewController(GObject.Object):

    def __init__(self, rigo_service, work_box):
        self._service = rigo_service
        self._box = work_box

    def _setup_terminal_menu(self):
        """
        Setup TerminalWidget Right Click popup-menu.
        """
        self._terminal_menu = Gtk.Menu()

        sall_menu_item = Gtk.ImageMenuItem.new_from_stock(
            "gtk-select-all", None)
        sall_menu_item.connect("activate", self._on_terminal_select_all)
        self._terminal_menu.append(sall_menu_item)

        copy_menu_item = Gtk.ImageMenuItem.new_from_stock(
            "gtk-copy", None)
        copy_menu_item.connect("activate", self._on_terminal_copy)
        self._terminal_menu.append(copy_menu_item)

        reset_menu_item = Gtk.ImageMenuItem.new_from_stock(
            "gtk-clear", None)
        reset_menu_item.connect("activate", self._on_terminal_reset)
        self._terminal_menu.append(reset_menu_item)

        self._terminal_menu.show_all()

    def _setup_terminal_area(self):
        """
        Setup TerminalWidget area (including ScrollBar).
        """
        hbox = Gtk.HBox()

        self._terminal = TerminalWidget()
        self._terminal.connect(
            "button-press-event",
            self._on_terminal_click)
        self._terminal.reset()
        hbox.pack_start(self._terminal, True, True, 0)

        scrollbar = Gtk.VScrollbar.new(self._terminal.adjustment)
        hbox.pack_start(scrollbar, False, False, 0)
        hbox.show_all()

        return hbox

    def _setup_progress_area(self):
        """
        Setup Progress Bar area.
        """
        self._progress_box = Gtk.VBox()

        progress_align = Gtk.Alignment()
        progress_align.set_padding(10, 10, 0, 0)
        self._progress_bar = Gtk.ProgressBar()
        progress_align.add(self._progress_bar)
        self._progress_box.pack_start(progress_align, False, False, 0)
        self._progress_box.show_all()

        return self._progress_box

    def setup(self):
        """
        Initialize WorkViewController controlled resources.
        """
        self._setup_terminal_menu()

        box = self._setup_progress_area()
        self._box.pack_start(box, False, False, 0)

        box = self._setup_terminal_area()
        self._box.pack_start(box, True, True, 0)

        self._service.set_terminal(self._terminal)
        self._service.set_work_controller(self)

        self.deactivate_progress_bar()
        self.deactivate_app_box()

    def activate_app_box(self):
        """
        Activate the Application Box showing information
        about the Application being currently handled.
        """
        # FIXME, complete

    def deactivate_app_box(self):
        """
        Deactivate the Application Box showing information
        about the Application being currently handled.
        """
        # FIXME, complete

    def activate_progress_bar(self):
        """
        Activate the Progress Bar showing progress information.
        """
        self._progress_box.show_all()

    def deactivate_progress_bar(self):
        """
        Deactivate the Progress Bar showing progress information.
        """
        self._progress_box.hide()

    def set_progress(self, fraction, text=None):
        """
        Set Progress Bar progress, progress must be a value between
        0.0 and 1.0. You can also provide a new text for progress at
        the same time, the same will be escaped and cleaned out
        by the callee.
        """
        self._progress_bar.set_fraction(fraction)
        if text is not None:
            self._progress_bar.set_text(escape_markup(text))

    def set_progress_text(self, text):
        """
        Set Progress Bar text. The same will be escaped and cleaned out by
        the callee.
        """
        self._progress_bar.set_text(escape_markup(text))

    def _on_terminal_click(self, widget, event):
        """
        Right Click on the TerminalWidget area.
        """
        if event.button == 3:
            self._terminal_menu.popup(
                None, None, None, None, event.button, event.time)

    def _on_terminal_copy(self, widget):
        """
        Copy to clipboard Terminal GtkMenuItem clicked.
        """
        self._terminal.copy_clipboard()

    def _on_terminal_reset(self, widget):
        """
        Reset Terminal GtkMenuItem clicked.
        """
        self._terminal.reset()

    def _on_terminal_select_all(self, widget):
        """
        Select All Terminal GtkMenuItem clicked.
        """
        self._terminal.select_all()


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
            GLib.idle_add(self.emit, "view-want-change", Rigo.WORK_VIEW_STATE)
            return
        if text == "rigo:output":
            GLib.idle_add(self.emit, "view-want-change", Rigo.WORK_VIEW_STATE)
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
        self._service.update_repositories(
            self._entropy.repositories(), True)

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


class NotificationViewController(GObject.Object):

    """
    Notification area widget controller.
    This class features the handling of some built-in
    Notification objects (like updates and outdated repositories)
    but also accepts external NotificationBox instances as well.
    """

    def __init__(self, activity_rwsem, entropy_client, entropy_ws, rigo_service,
                 avc, notification_box):
        GObject.Object.__init__(self)
        self._activity_rwsem = activity_rwsem
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._service = rigo_service
        self._avc = avc
        self._box = notification_box
        self._updates = None
        self._security_updates = None
        self._context_id_map = {}

    def setup(self):
        GLib.timeout_add(3000, self._calculate_updates)
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

    def __order_updates(self, updates):
        """
        Order updates using PN.
        """
        def _key_func(x):
            return self._entropy.open_repository(
                x[1]).retrieveName(x[0]).lower()
        return sorted(updates, key=_key_func)

    def __calculate_updates(self):
        self._activity_rwsem.reader_acquire()
        try:
            if Repository.are_repositories_old():
                GLib.idle_add(self._notify_old_repositories_safe)
                return

            updates, removal, fine, spm_fine = \
                self._entropy.calculate_updates()
            self._updates = self.__order_updates(updates)
            self._security_updates = self._entropy.calculate_security_updates()
        finally:
            self._activity_rwsem.reader_release()

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
        Add NotificationBox signaling the user that repositories
        are old..
        """
        box = RepositoriesUpdateNotificationBox(
            self._entropy, self._avc)
        box.connect("update-request", self._on_update)
        self.append(box)

    def _on_upgrade(self, *args):
        """
        Callback requesting Packages Update.
        """
        # FIXME, lxnay complete
        print("On Upgrade Request Received", args)
        # FIXME, this is for testing, REMOVE !!!!
        self._service.update_repositories(self._entropy.repositories(), True)

    def _on_update(self, *args):
        """
        Callback requesting Repositories Update.
        """
        # FIXME, lxnay complete
        print("On Update Request Received", args)
        self._service.update_repositories(self._entropy.repositories(), True)

    def _on_update_show(self, *args):
        """
        Callback from UpdatesNotification "Show" button.
        Showing updates.
        """
        self._avc.set_many_safe(self._updates)

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
            self._context_id_map.pop(box.get_context_id(), None)
            box.destroy()

    def remove_safe(self, box):
        """
        Thread-safe version of remove().
        """
        GLib.idle_add(self.remove, box)

    def clear(self):
        """
        Clear all the notifications.
        """
        for child in self._box.get_children():
            child.destroy()
        self._context_id_map.clear()

    def clear_safe(self):
        """
        Thread-safe version of clear().
        """
        GLib.idle_add(self.clear)


class ApplicationViewController(GObject.Object):
    """
    Applications View Container, exposing all the events
    that can happen to Applications listed in the contained
    TreeView.
    """

    class WindowedReactiveStar(ReactiveStar):

        def __init__(self, window):
            self._window = window
            self._hand = Gdk.Cursor.new(Gdk.CursorType.HAND2)
            ReactiveStar.__init__(self)

        def on_enter_notify(self, widget, event):
            self._window.get_window().set_cursor(self._hand)

        def on_leave_notify(self, widget, event):
            self._window.get_window().set_cursor(None)

    __gsignals__ = {
        # Double click on application widget
        "application-activated"  : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        # Show Application in the Rigo UI
        "application-show"  : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        # Hide Application in the Rigo UI
        "application-hide"  : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        # Single click on application widget
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        # action requested for application
        "application-request-action" : (GObject.SignalFlags.RUN_LAST,
                                        None,
                                        (GObject.TYPE_PYOBJECT,
                                         str),
                                       ),
    }

    VOTE_NOTIFICATION_CONTEXT_ID = "VoteNotificationContext"
    COMMENT_NOTIFICATION_CONTEXT_ID = "CommentNotificationContext"

    def __init__(self, entropy_client, entropy_ws, builder):
        GObject.Object.__init__(self)
        self._builder = builder
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._app_store = None
        self._last_app = None
        self._nc = None
        self._avc = None

        self._window = self._builder.get_object("rigoWindow")
        self._image = self._builder.get_object("appViewImage")
        self._app_name_lbl = self._builder.get_object("appViewNameLabel")
        self._app_info_lbl = self._builder.get_object("appViewInfoLabel")
        self._app_downloaded_lbl = self._builder.get_object(
            "appViewDownloadedLabel")
        self._app_comments_box = self._builder.get_object("appViewCommentsVbox")
        self._app_comments_box.set_name("comments-box")
        self._app_comments_align = self._builder.get_object(
            "appViewCommentsAlign")
        self._app_my_comments_box = self._builder.get_object(
            "appViewMyCommentsVbox")
        self._app_my_comments_align = self._builder.get_object(
            "appViewMyCommentsAlign")
        self._app_my_comments_box.set_name("comments-box")
        self._app_comment_send_button = self._builder.get_object(
            "appViewCommentSendButton")
        self._app_comment_text_view = self._builder.get_object(
            "appViewCommentText")
        self._app_comment_text_view.set_name("rigo-text-view")
        self._app_comment_text_buffer = self._builder.get_object(
            "appViewCommentTextBuffer")
        self._app_comment_more_label = self._builder.get_object(
            "appViewCommentMoreLabel")
        self._stars_container = self._builder.get_object("appViewStarsSelVbox")
        self._app_button_area = self._builder.get_object("appViewButtonArea")

        self._stars = ApplicationViewController.WindowedReactiveStar(
            self._window)
        self._stars_alignment = Gtk.Alignment.new(0.0, 0.5, 1.0, 1.0)
        self._stars_alignment.set_padding(0, 5, 0, 0)
        self._stars_alignment.add(self._stars)
        self._stars.set_size_as_pixel_value(24)

        self._stars_container.pack_start(self._stars_alignment, False, False, 0)

        self._app_images_box = self._builder.get_object(
            "appViewImagesVbox")

    def set_notification_controller(self, nc):
        """
        Bind NotificationController object to this class.
        """
        self._nc = nc

    def set_applications_controller(self, avc):
        """
        Bind ApplicationsViewController object to this class.
        """
        self._avc = avc

    def set_store(self, store):
        """
        Bind AppListStore object to this class.
        """
        self._app_store = store

    def setup(self):
        self.connect("application-activated", self._on_application_activated)
        self._app_store.connect("redraw-request", self._on_redraw_request)
        self._app_comment_send_button.connect("clicked", self._on_send_comment)
        self._app_comment_send_button.set_sensitive(False)
        self._app_comment_text_buffer.connect(
            "changed", self._on_comment_buffer_changed)
        self._stars.connect("changed", self._on_stars_clicked)

    def _on_comment_buffer_changed(self, widget):
        """
        Our comment text is changed, decide if to activate the Send button.
        """
        count = self._app_comment_text_buffer.get_char_count()
        found = count != 0
        self._app_comment_send_button.set_sensitive(found)

    def _on_application_activated(self, avc, app):
        """
        Event received from Gtk widgets requesting us to load package
        information. Once we're done loading the shit, we just emit
        'application-show' and let others do the UI switch.
        """
        self._last_app = app
        task = ParallelTask(self.__application_activate, app)
        task.name = "ApplicationActivate"
        task.daemon = True
        task.start()

    def _on_redraw_request(self, widget, pkg_match):
        """
        Redraw request received from AppListStore for given package match.
        We are required to update rating, number of downloads, icon.
        """
        if self._last_app is None:
            return
        if pkg_match == self._last_app.get_details().pkg:
            stats = self._app_store.get_review_stats(pkg_match)
            icon = self._app_store.get_icon(pkg_match)
            self._setup_application_stats(stats, icon)
            if self._app_store is not None:
                self._app_store.emit("redraw-request", self._app_store)

    def _on_stars_clicked(self, widget, app=None):
        """
        Stars clicked, user wants to vote.
        """
        if app is None:
            app = self._last_app
            if app is None:
                # wtf
                return

        def _sender(app, vote):
            if not app.is_webservice_available():
                GLib.idle_add(self._notify_webservice_na, app,
                              self.VOTE_NOTIFICATION_CONTEXT_ID)
                return
            ws_user = app.get_webservice_username()
            if ws_user is not None:
                GLib.idle_add(self._notify_vote_submit, app, ws_user, vote)
            else:
                GLib.idle_add(self._notify_login_request, app, vote,
                              self._on_stars_login_success,
                              self._on_stars_login_failed,
                              self.VOTE_NOTIFICATION_CONTEXT_ID)

        vote = int(self._stars.get_rating()) # is float
        task = ParallelTask(_sender, app, vote)
        task.name = "AppViewSendVote"
        task.start()

    def _on_stars_login_success(self, widget, username, app):
        """
        Notify user that we successfully logged in!
        """
        box = NotificationBox(
            _("Logged in as <b>%s</b>! How about your <b>vote</b>?") \
                % (escape_markup(username),),
            message_type=Gtk.MessageType.INFO,
            context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)

        def _send_vote(widget):
            self._on_stars_clicked(self._stars, app=app)
        box.add_button(_("_Vote now"), _send_vote)

        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _on_stars_login_failed(self, widget, app):
        """
        Entropy Web Services Login failed message.
        """
        box = NotificationBox(
            _("Login failed. Your <b>vote</b> hasn't been added"),
            message_type=Gtk.MessageType.ERROR,
            context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
        box.add_destroy_button(_("_Ok, thanks"))
        self._nc.append(box)

    def _notify_vote_submit(self, app, username, vote):
        """
        Notify User about Comment submission with current credentials.
        """
        box = NotificationBox(
            _("Rate <b>%s</b> as <b>%s</b>, with <b>%d</b> stars?") \
                % (app.name, escape_markup(username),
                   vote,),
            message_type=Gtk.MessageType.INFO,
            context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)

        def _vote_submit(widget):
            self._vote_submit(app, username, vote)
        box.add_button(_("_Ok, cool!"), _vote_submit)

        def _send_vote():
            self._on_stars_clicked(self._stars, app=app)
        def _logout_webservice(widget):
            self._logout_webservice(app, _send_vote)
        box.add_button(_("_No, logout!"), _logout_webservice)

        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _vote_submit(self, app, username, vote):
        """
        Do the actual vote submit.
        """
        task = ParallelTask(
            self._vote_submit_thread_body,
            app, username, vote)
        task.name = "VoteSubmitThreadBody"
        task.daemon = True
        task.start()

    def _vote_submit_thread_body(self, app, username, vote):
        """
        Called by _vote_submit(), does the actualy submit.
        """
        repository_id = app.get_details().channelname
        webserv = self._entropy_ws.get(repository_id)
        if webserv is None:
            # impossible!
            return

        key = app.get_details().pkgkey

        err_msg = None
        try:
            voted = webserv.add_vote(
                key, vote)
        except WebService.WebServiceException as err:
            voted = False
            err_msg = str(err)

        def _submit_success():
            nbox = NotificationBox(
                _("Your vote has been added!"),
                message_type=Gtk.MessageType.INFO,
                context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
            nbox.add_destroy_button(_("Ok, great!"))
            self._nc.append(nbox, timeout=10)
            self._on_redraw_request(None, app.get_details().pkg)

        def _submit_fail(err_msg):
            if err_msg is None:
                box = NotificationBox(
                    _("You already voted this <b>Application</b>"),
                    message_type=Gtk.MessageType.ERROR,
                    context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
            else:
                box = NotificationBox(
                    _("Vote error: <i>%s</i>") % (err_msg,),
                    message_type=Gtk.MessageType.ERROR,
                    context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
            box.add_destroy_button(_("Ok, thanks"))
            self._nc.append(box)

        if voted:
            GLib.idle_add(_submit_success)
        else:
            GLib.idle_add(_submit_fail, err_msg)

    def __application_activate(self, app):
        """
        Collect data from app, then call the UI setup in the main loop.
        """
        details = app.get_details()
        metadata = {}
        metadata['markup'] = app.get_extended_markup()
        metadata['info'] = app.get_info_markup()
        metadata['download_size'] = details.downsize
        metadata['stats'] = app.get_review_stats()
        metadata['homepage'] = details.website
        metadata['date'] = details.date
        # using app store here because we cache the icon pixbuf
        metadata['icon'] = self._app_store.get_icon(details.pkg)
        metadata['is_installed'] = app.is_installed()
        metadata['is_updatable'] = app.is_updatable()
        GLib.idle_add(self._setup_application_info, app, metadata)

    def hide(self):
        """
        This method shall be called when the Controller widgets are
        going to hide.
        """
        self._last_app = None
        for child in self._app_my_comments_box.get_children():
            child.destroy()
        for child in self._app_images_box.get_children():
            child.destroy()

        self.emit("application-hide", self)

    def _on_send_comment(self, widget, app=None):
        """
        Send comment to Web Service.
        """
        if app is None:
            app = self._last_app
            if app is None:
                # we're hiding
                return

        text = self._app_comment_text_buffer.get_text(
            self._app_comment_text_buffer.get_start_iter(),
            self._app_comment_text_buffer.get_end_iter(),
            False)
        if not text.strip():
            return
        # make it utf-8
        text = const_convert_to_unicode(text, enctype=etpConst['conf_encoding'])

        def _sender(app, text):
            if not app.is_webservice_available():
                GLib.idle_add(self._notify_webservice_na, app,
                              self.COMMENT_NOTIFICATION_CONTEXT_ID)
                return
            ws_user = app.get_webservice_username()
            if ws_user is not None:
                GLib.idle_add(self._notify_comment_submit, app, ws_user, text)
            else:
                GLib.idle_add(self._notify_login_request, app, text,
                              self._on_comment_login_success,
                              self._on_comment_login_failed,
                              self.COMMENT_NOTIFICATION_CONTEXT_ID)

        task = ParallelTask(_sender, app, text)
        task.name = "AppViewSendComment"
        task.start()

    def _notify_webservice_na(self, app, context_id):
        """
        Notify Web Service unavailability for given Application object.
        """
        box = NotificationBox(
            "%s: <b>%s</b>" % (
                _("Entropy Web Services not available for repository"),
                app.get_details().channelname),
            message_type=Gtk.MessageType.ERROR,
            context_id=context_id)
        box.add_destroy_button(_("Ok, thanks"))
        self._nc.append(box)

    def _notify_comment_submit(self, app, username, text):
        """
        Notify User about Comment submission with current credentials.
        """
        box = NotificationBox(
            _("You are about to add a <b>comment</b> as <b>%s</b>.") \
                % (escape_markup(username),),
            message_type=Gtk.MessageType.INFO,
            context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)

        def _comment_submit(widget):
            self._comment_submit(app, username, text)
        box.add_button(_("_Ok, cool!"), _comment_submit)

        def _send_comment():
            self._on_send_comment(None, app=app)
        def _logout_webservice(widget):
            self._logout_webservice(app, _send_comment)
        box.add_button(_("_No, logout!"), _logout_webservice)

        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _comment_submit(self, app, username, text):
        """
        Actual Comment submit to Web Service.
        Here we arrive from the MainThread.
        """
        task = ParallelTask(
            self._comment_submit_thread_body,
            app, username, text)
        task.name = "CommentSubmitThreadBody"
        task.daemon = True
        task.start()

    def _comment_submit_thread_body(self, app, username, text):
        """
        Called by _comment_submit(), does the actualy submit.
        """
        repository_id = app.get_details().channelname
        webserv = self._entropy_ws.get(repository_id)
        if webserv is None:
            # impossible!
            return

        key = app.get_details().pkgkey
        doc_factory = webserv.document_factory()
        doc = doc_factory.comment(
            username, text, "", "")

        err_msg = None
        try:
            new_doc = webserv.add_document(key, doc)
        except WebService.WebServiceException as err:
            new_doc = None
            err_msg = str(err)

        def _submit_success(doc):
            box = CommentBox(self._nc, self._avc, webserv, doc, is_last=True)
            box.connect("destroy", self._on_comment_box_destroy)

            self.__clean_my_non_comment_boxes()
            box.render()
            self._app_my_comments_box.pack_start(box, False, False, 2)
            box.show()
            self._app_my_comments_box.show()

            nbox = NotificationBox(
                _("Your comment has been submitted!"),
                message_type=Gtk.MessageType.INFO,
                context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
            nbox.add_destroy_button(_("Ok, great!"))
            self._app_comment_text_buffer.set_text("")
            self._nc.append(nbox, timeout=10)

        def _submit_fail():
            box = NotificationBox(
                _("Comment submit error: <i>%s</i>") % (err_msg,),
                message_type=Gtk.MessageType.ERROR,
                context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
            box.add_destroy_button(_("Ok, thanks"))
            self._nc.append(box)

        if new_doc is not None:
            GLib.idle_add(_submit_success, new_doc)
        else:
            GLib.idle_add(_submit_fail)

    def _logout_webservice(self, app, reinit_callback):
        """
        Execute logout of current credentials from Web Service.
        Actually, this means removing the local cookie.
        """
        repository_id = app.get_details().channelname
        webserv = self._entropy_ws.get(repository_id)
        if webserv is not None:
            webserv.remove_credentials()

        GLib.idle_add(self._avc.emit, "logged-out")
        GLib.idle_add(reinit_callback)

    def _notify_login_request(self, app, text, on_success, on_fail,
                              context_id):
        """
        Notify User that login is required
        """
        box = LoginNotificationBox(
            self._avc, self._entropy_ws, app,
            context_id=context_id)
        box.connect("login-success", on_success)
        box.connect("login-failed", on_fail)
        self._nc.append(box)

    def _on_comment_login_success(self, widget, username, app):
        """
        Notify user that we successfully logged in!
        """
        box = NotificationBox(
            _("Logged in as <b>%s</b>! How about your <b>comment</b>?") \
                % (escape_markup(username),),
            message_type=Gtk.MessageType.INFO,
            context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
        def _send_comment(widget):
            self._on_send_comment(widget, app=app)
        box.add_button(_("_Send now"), _send_comment)
        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _on_comment_login_failed(self, widget, app):
        """
        Entropy Web Services Login failed message.
        """
        box = NotificationBox(
            _("Login failed. Your <b>comment</b> hasn't been added"),
            message_type=Gtk.MessageType.ERROR,
            context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
        box.add_destroy_button(_("_Ok, thanks"))
        self._nc.append(box)

    def _on_comment_box_destroy(self, widget):
        """
        Called when a CommentBox is destroyed.
        We need to figure out if there are CommentBoxes left and in case
        show the "no comments available" message.
        """
        children = self._app_comments_box.get_children()
        if not children:
            self.__show_no_comments()

    def __show_no_comments(self):
        """
        Create "No comments for this Application" message.
        """
        label = Gtk.Label()
        label.set_markup(
            prepare_markup(
                _("<i>No <b>comments</b> for this Application, yet!</i>")))
        # place in app_my, this way it will get cleared out
        # once a new comment is inserted
        self._app_my_comments_box.pack_start(label, False, False, 1)
        self._app_my_comments_box.show_all()

    def __clean_non_comment_boxes(self):
        """
        Remove children that are not CommentBox objects from
        self._app_comments_box
        """
        for child in self._app_comments_box.get_children():
            if not isinstance(child, CommentBox):
                child.destroy()

    def __clean_my_non_comment_boxes(self):
        """
        Remove children that are not CommentBox objects from
        self._app_my_comments_box
        """
        for child in self._app_my_comments_box.get_children():
            if not isinstance(child, CommentBox):
                child.destroy()

    def __clean_non_image_boxes(self):
        """
        Remove children that are not ImageBox objects from
        self._app_images_box
        """
        for child in self._app_images_box.get_children():
            if not isinstance(child, ImageBox):
                child.destroy()

    def _append_comments(self, downloader, app, comments, has_more):
        """
        Append given Entropy WebService Document objects to
        the comment area.
        """
        self.__clean_non_comment_boxes()
        # make sure we didn't leave stuff here as well
        self.__clean_my_non_comment_boxes()

        if not comments:
            self.__show_no_comments()
            return

        if has_more:
            button_box = Gtk.HButtonBox()
            button = Gtk.Button()
            button.set_label(_("Older comments"))
            button.set_alignment(0.5, 0.5)
            def _enqueue_download(widget):
                widget.get_parent().destroy()
                spinner = Gtk.Spinner()
                spinner.set_size_request(24, 24)
                spinner.set_tooltip_text(_("Loading older comments..."))
                spinner.set_name("comment-box-spinner")
                self._app_comments_box.pack_end(spinner, False, False, 3)
                spinner.show()
                spinner.start()
                downloader.enqueue_download()
            button.connect("clicked", _enqueue_download)

            button_box.pack_start(button, False, False, 0)
            self._app_comments_box.pack_start(button_box, False, False, 1)
            button_box.show_all()

        idx = 0
        length = len(comments)
        # can be None
        webserv = self._entropy_ws.get(app.get_details().channelname)
        for doc in comments:
            idx += 1
            box = CommentBox(
                self._nc, self._avc, webserv, doc,
                is_last=(not has_more and (idx == length)))
            box.connect("destroy", self._on_comment_box_destroy)
            box.render()
            self._app_comments_box.pack_end(box, False, False, 2)
            box.show()

    def _append_comments_safe(self, downloader, app, comments, has_more):
        """
        Same as _append_comments() but thread-safe.
        """
        GLib.idle_add(self._append_comments, downloader, app,
                      comments, has_more)

    def _append_images(self, downloader, app, images, has_more):
        """
        Append given Entropy WebService Document objects to
        the images area.
        """
        self.__clean_non_image_boxes()

        if not images:
            label = Gtk.Label()
            label.set_markup(
                prepare_markup(
                    _("<i>No <b>images</b> for this Application, yet!</i>")))
            self._app_images_box.pack_start(label, False, False, 1)
            label.show()
            return

        if has_more:
            button_box = Gtk.HButtonBox()
            button = Gtk.Button()
            button.set_label(_("Older images"))
            button.set_alignment(0.5, 0.5)
            def _enqueue_download(widget):
                widget.get_parent().destroy()
                spinner = Gtk.Spinner()
                spinner.set_size_request(24, 24)
                spinner.set_tooltip_text(_("Loading older images..."))
                spinner.set_name("image-box-spinner")
                self._app_images_box.pack_end(spinner, False, False, 3)
                spinner.show()
                spinner.start()
                downloader.enqueue_download()
            button.connect("clicked", _enqueue_download)

            button_box.pack_start(button, False, False, 0)
            self._app_images_box.pack_start(button_box, False, False, 1)
            button_box.show_all()

        idx = 0
        length = len(images)
        for doc in images:
            idx += 1
            box = ImageBox(doc, is_last=(not has_more and (idx == length)))
            box.render()
            self._app_images_box.pack_end(box, False, False, 2)
            box.show()

    def _append_images_safe(self, downloader, app, comments, has_more):
        """
        Same as _append_images() but thread-safe.
        """
        GLib.idle_add(self._append_images, downloader, app,
                      comments, has_more)

    def _on_app_remove(self, widget, app):
        """
        Remove the given Application.
        """
        self.emit("application-request-action",
                  app, AppActions.REMOVE)

    def _on_app_install(self, widget, app):
        """
        Install (or reinstall) the given Application.
        """
        self.emit("application-request-action",
                  app, AppActions.INSTALL)

    def _setup_buttons(self, app, is_installed, is_updatable):
        """
        Setup Application View Buttons (Install/Remove/Update).
        """
        button_area = self._app_button_area
        for child in button_area.get_children():
            child.destroy()

        if is_installed:
            if is_updatable:
                update_button = Gtk.Button()
                update_button.set_label(
                    escape_markup(_("Update")))
                def _on_app_update(widget):
                    return self._on_app_install(widget, app)
                update_button.connect("clicked", _on_app_update)
                button_area.pack_start(update_button, False, False, 0)
            else:
                reinstall_button = Gtk.Button()
                reinstall_button.set_label(
                    escape_markup(_("Reinstall")))
                def _on_app_reinstall(widget):
                    return self._on_app_install(widget, app)
                reinstall_button.connect("clicked", _on_app_reinstall)
                button_area.pack_start(reinstall_button, False, False, 0)

            remove_button = Gtk.Button()
            remove_button.set_label(
                escape_markup(_("Remove")))
            def _on_app_remove(widget):
                return self._on_app_remove(widget, app)
            remove_button.connect("clicked", _on_app_remove)
            button_area.pack_start(remove_button, False, False, 0)

        else:
            install_button = Gtk.Button()
            install_button.set_label(
                escape_markup(_("Install")))
            def _on_app_install(widget):
                return self._on_app_install(widget, app)
            install_button.connect("clicked", _on_app_install)
            button_area.pack_start(install_button, False, False, 0)

        button_area.show_all()

    def _setup_application_stats(self, stats, icon):
        """
        Setup widgets related to Application statistics (and icon).
        """
        total_downloads = stats.downloads_total
        if total_downloads < 0:
            down_msg = escape_markup(_("Not available"))
        elif not total_downloads:
            down_msg = escape_markup(_("Never downloaded"))
        else:
            down_msg = "<small><b>%s</b> %s</small>" % (
                stats.downloads_total_markup,
                escape_markup(_("downloads")),)

        self._app_downloaded_lbl.set_markup(down_msg)
        if icon:
            self._image.set_from_pixbuf(icon)
        self._stars.set_rating(stats.ratings_average)
        self._stars_alignment.show_all()

    def _setup_application_info(self, app, metadata):
        """
        Setup the actual UI widgets content and emit 'application-show'
        """
        self._app_name_lbl.set_markup(metadata['markup'])
        self._app_info_lbl.set_markup(metadata['info'])

        # install/remove/update buttons
        self._setup_buttons(
            app, metadata['is_installed'],
            metadata['is_updatable'])

        # only comments supported, point to the remote
        # www service for the rest
        self._app_comment_more_label.set_markup(
            "<b>%s</b>: <a href=\"%s\">%s</a>" % (
                escape_markup(_("Want to add images, etc?")),
                escape_markup(build_application_store_url(app, "ugc")),
                escape_markup(_("click here!")),))

        stats = metadata['stats']
        icon = metadata['icon']
        self._setup_application_stats(stats, icon)

        # load application comments asynchronously
        # so at the beginning, just place a spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(-1, 48)
        spinner.set_tooltip_text(escape_markup(_("Loading comments...")))
        spinner.set_name("comment-box-spinner")
        for child in self._app_comments_box.get_children():
            child.destroy()
        self._app_comments_box.pack_start(spinner, False, False, 0)
        spinner.show()
        spinner.start()

        downloader = ApplicationViewController.MetadataDownloader(
            app, self, self._append_comments_safe,
            app.download_comments)
        downloader.start()

        downloader = ApplicationViewController.MetadataDownloader(
            app, self, self._append_images_safe,
            app.download_images)
        downloader.start()

        self.emit("application-show", app)

    class MetadataDownloader(GObject.Object):
        """
        Automated Application comments downloader.
        """

        def __init__(self, app, avc, callback, app_downloader_method):
            self._app = app
            self._avc = avc
            self._offset = 0
            self._callback = callback
            self._task = ParallelTask(self._download)
            self._app_downloader = app_downloader_method

        def start(self):
            """
            Start downloading comments and send them to callback.
            Loop over until we have more of them to download.
            """
            self._offset = 0
            self._task.start()

        def _download_callback(self, document_list):
            """
            Callback called by download_<something>() once data
            is arrived from web service.
            document_list can be None!
            """
            has_more = 0
            if document_list is not None:
                has_more = document_list.has_more()
            # stash more data?
            if has_more and (document_list is not None):
                self._offset += len(document_list)
                # download() will be called externally

            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "MetadataDownloader._download_callback: %s, more: %s" % (
                        document_list, has_more))
                if document_list is not None:
                    const_debug_write(
                        __name__,
                        "MetadataDownloader._download_callback: "
                            "total: %s, offset: %s" % (
                            document_list.total(), document_list.offset()))

            self._callback(self, self._app, document_list, has_more)

        def reset_offset(self):
            """
            Reset Metadata download offset to 0.
            """
            self._offset = 0

        def get_offset(self):
            """
            Get current Metadata download offset.
            """
            return self._offset

        def enqueue_download(self):
            """
            Enqueue a new download, starting from current offset
            """
            self._task = ParallelTask(self._download)
            self._task.start()

        def _download(self):
            """
            Thread body of the initial Metadata downloader.
            """
            self._app_downloader(self._download_callback,
                                 offset=self._offset)


class Rigo(Gtk.Application):

    class RigoHandler(object):

        def __init__(self, rigo_app):
            self._app = rigo_app

        def onDeleteWindow(self, window, event):
            # if UI is locked, do not allow to close Rigo
            if self._app.is_ui_locked():
                rc = self._app._show_yesno_dialog(
                    None,
                    escape_markup(_("Hey hey hey!")),
                    escape_markup(_("Rigo is working, are you sure?")))
                if rc == Gtk.ResponseType.NO:
                    return True

            while True:
                try:
                    entropy.tools.kill_threads()
                    Gtk.main_quit((window, event))
                except KeyboardInterrupt:
                    continue
                break

    # Possible Rigo Application UI States
    BROWSER_VIEW_STATE, STATIC_VIEW_STATE, \
        APPLICATION_VIEW_STATE, \
        WORK_VIEW_STATE = range(4)

    def __init__(self):
        self._current_state_lock = False
        self._current_state = Rigo.STATIC_VIEW_STATE
        self._state_transactions = {
            Rigo.BROWSER_VIEW_STATE: (
                self._enter_browser_state,
                self._exit_browser_state),
            Rigo.STATIC_VIEW_STATE: (
                self._enter_static_state,
                self._exit_static_state),
            Rigo.APPLICATION_VIEW_STATE: (
                self._enter_application_state,
                self._exit_application_state),
            Rigo.WORK_VIEW_STATE: (
                self._enter_work_state,
                self._exit_work_state),
        }
        self._state_mutex = Lock()

        icons = get_sc_icon_theme(DATA_DIR)
        app_handler = Rigo.RigoHandler(self)

        self._activity_rwsem = ReadersWritersSemaphore()
        self._entropy = Client()
        self._entropy_ws = EntropyWebService(self._entropy)
        self._service = RigoServiceController(
            self, self._activity_rwsem,
            self._entropy, self._entropy_ws)

        self._builder = Gtk.Builder()
        self._builder.add_from_file(os.path.join(DATA_DIR, "ui/gtk3/rigo.ui"))
        self._builder.connect_signals(app_handler)
        self._window = self._builder.get_object("rigoWindow")
        self._window.set_name("rigo-view")
        self._apps_view = self._builder.get_object("appsViewVbox")
        self._scrolled_view = self._builder.get_object("appsViewScrolledWindow")
        self._app_view = self._builder.get_object("appViewScrollWin")
        self._app_view.set_name("rigo-view")
        self._app_view_port = self._builder.get_object("appViewVport")
        self._app_view_port.set_name("rigo-view")
        self._not_found_box = self._builder.get_object("appsViewNotFoundVbox")
        self._search_entry = self._builder.get_object("searchEntry")
        self._static_view = self._builder.get_object("staticViewVbox")
        self._notification = self._builder.get_object("notificationBox")
        self._work_view = self._builder.get_object("workViewVbox")
        self._work_view.set_name("rigo-view")

        self._app_view_c = ApplicationViewController(
            self._entropy, self._entropy_ws, self._builder)

        self._view = AppTreeView(self._entropy, self._app_view_c, icons, True,
                                 AppListStore.ICON_SIZE, store=None)
        self._scrolled_view.add(self._view)

        self._app_store = AppListStore(
            self._entropy, self._entropy_ws,
            self._view, icons)
        def _queue_draw(*args):
            self._view.queue_draw()
        self._app_store.connect("redraw-request", _queue_draw)

        self._app_view_c.set_store(self._app_store)
        self._app_view_c.connect("application-show",
            self._on_application_show)

        self._welcome_box = WelcomeBox()

        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-error-bell", False)
        # wire up the css provider to reconfigure on theme-changes
        self._window.connect("style-updated",
                                 self._on_style_updated,
                                 init_sc_css_provider,
                                 settings,
                                 Gdk.Screen.get_default(),
                                 DATA_DIR)

        self._avc = ApplicationsViewController(
            self._activity_rwsem,
            self._entropy, self._entropy_ws, self._service,
            icons, self._not_found_box,
            self._search_entry, self._app_store, self._view)

        self._avc.connect("view-cleared", self._on_view_cleared)
        self._avc.connect("view-filled", self._on_view_filled)
        self._avc.connect("view-want-change", self._on_view_change)

        self._nc = NotificationViewController(
            self._activity_rwsem, self._entropy,
            self._entropy_ws, self._service,
            self._avc, self._notification)

        self._app_view_c.set_notification_controller(self._nc)
        self._app_view_c.set_applications_controller(self._avc)

        self._service.set_applications_controller(self._avc)
        self._service.set_notification_controller(self._nc)

        self._service.connect("repositories-updating", self._on_repo_updating)
        self._service.connect("repositories-updated", self._on_repo_updated)

        self._work_view_c = WorkViewController(
            self._service, self._work_view)

    def is_ui_locked(self):
        """
        Return whether the UI is currently locked.
        """
        return self._current_state_lock

    def _on_repo_updating(self, widget, state):
        """
        Emitted by RigoServiceController when we're asked to
        lock down the UI to a given state.
        """
        self._search_entry.set_sensitive(False)
        self._change_view_state(state, lock=True)

    def _on_repo_updated(self, widget):
        """
        Emitted by RigoServiceController when we're allowed to
        let the user mess again with the UI.
        """
        with self._state_mutex:
            self._current_state_lock = False
        self._search_entry.set_sensitive(True)

    def _on_view_cleared(self, *args):
        self._change_view_state(Rigo.STATIC_VIEW_STATE)

    def _on_view_filled(self, *args):
        self._change_view_state(Rigo.BROWSER_VIEW_STATE)

    def _on_view_change(self, widget, state):
        self._change_view_state(state)

    def _on_application_show(self, *args):
        self._change_view_state(Rigo.APPLICATION_VIEW_STATE)

    def _exit_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._apps_view.hide()

    def _enter_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._apps_view.show()

    def _exit_static_state(self):
        """
        Action triggered when UI exits the Static Browser
        state (or mode). AKA the Welcome Box.
        """
        self._static_view.hide()
        # release all the childrens of static_view
        for child in self._static_view.get_children():
            self._static_view.remove(child)

    def _enter_static_state(self):
        """
        Action triggered when UI exits the Static Browser
        state (or mode). AKA the Welcome Box.
        """
        # keep the current widget if any, or add the
        # welcome widget
        if not self._static_view.get_children():
            self._welcome_box.show()
            self._static_view.pack_start(self._welcome_box,
                                         True, True, 10)
        self._static_view.show()

    def _enter_application_state(self):
        """
        Action triggered when UI enters the Package Information
        state (or mode). Showing application information.
        """
        # change search_entry first icon to emphasize the
        # back action
        self._search_entry.set_icon_from_stock(
            Gtk.EntryIconPosition.PRIMARY,
            "gtk-go-back")
        self._app_view.show()

    def _exit_application_state(self):
        """
        Action triggered when UI exits the Package Information
        state (or mode). Hiding back application information.
        """
        self._search_entry.set_icon_from_stock(
            Gtk.EntryIconPosition.PRIMARY, "gtk-find")
        self._app_view.hide()
        self._app_view_c.hide()

    def _enter_work_state(self):
        """
        Action triggered when UI enters the Work View state (or mode).
        Either for Updating Repositories or Installing new Apps.
        """
        self._work_view.show()

    def _exit_work_state(self):
        """
        Action triggered when UI exits the Work View state (or mode).
        """
        self._work_view.hide()

    def _change_view_state(self, state, lock=False):
        """
        Change Rigo Application UI state.
        You can pass a custom widget that will be shown in case
        of static view state.
        """
        with self._state_mutex:
            if self._current_state_lock:
                const_debug_write(
                    __name__,
                    "cannot change view state, UI locked")
                return False
            txc = self._state_transactions.get(state)
            if txc is None:
                raise AttributeError("wrong view state")
            enter_st, exit_st = txc

            current_enter_st, current_exit_st = self._state_transactions.get(
                self._current_state)
            # exit from current state
            current_exit_st()
            # enter the new state
            enter_st()
            self._current_state = state
            if lock:
                self._current_state_lock = True

            return True

    def _change_view_state_safe(self, state):
        """
        Thread-safe version of change_view_state().
        """
        def _do_change():
            return self._change_view_state(state)
        GLib.idle_add(_do_change)

    def _on_style_updated(self, widget, init_css_callback, *args):
        """
        Gtk Style callback, nothing to see here.
        """
        init_css_callback(widget, *args)

    def _show_ok_dialog(self, parent, title, message):
        """
        Show ugly OK dialog window.
        """
        dlg = Gtk.MessageDialog(parent=parent,
                            type=Gtk.MessageType.INFO,
                            buttons=Gtk.ButtonsType.OK)
        dlg.set_markup(message)
        dlg.set_title(title)
        dlg.run()
        dlg.destroy()

    def _show_yesno_dialog(self, parent, title, message):
        """
        Show ugly OK dialog window.
        """
        dlg = Gtk.MessageDialog(parent=parent,
                            type=Gtk.MessageType.INFO,
                            buttons=Gtk.ButtonsType.YES_NO)
        dlg.set_markup(message)
        dlg.set_title(title)
        rc = dlg.run()
        dlg.destroy()
        return rc

    def _permissions_setup(self):
        """
        Check execution privileges and spawn the Rigo UI.
        """
        if not entropy.tools.is_user_in_entropy_group():
            # otherwise the lock handling would potentially
            # fail.
            self._show_ok_dialog(
                None,
                escape_markup(_("Not authorized")),
                escape_markup(_("You are not authorized to run Rigo")))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        acquired = not self._entropy.wait_resources(
            max_lock_count=1,
            shared=True)
        if not acquired:
            self._show_ok_dialog(
                None,
                escape_markup(_("Rigo")),
                escape_markup(_("Another Application Manager is active")))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        # check RigoDaemon, don't worry about races between Rigo Clients
        # it is fine to have multiple Rigo Clients connected. Mutual
        # exclusion is handled via Entropy Resources Lock (which is a file
        # based rwsem).
        activity = self._service.activity()
        if activity != ActivityStates.AVAILABLE:
            if activity == ActivityStates.NOT_AVAILABLE:
                msg = _("Background Service is currently not available")
            elif activity == ActivityStates.UPDATING_REPOSITORIES:
                # FIXME, jump to WORK_VIEW and show the progress.
                msg = _("Background Service is updating repositories")
            elif activity == ActivityStates.INSTALLING_APPLICATION:
                # FIXME, jump to WORK_VIEW and show the progress.
                msg = _("Background Service is installing Applications")
            elif activity == ActivityStates.UPGRADING_SYSTEM:
                # FIXME, jump to WORK_VIEW and show the progress.
                msg = _("Background Service is updating your system")
            elif activity == ActivityStates.INTERNAL_ROUTINES:
                msg = _("Background Service is currently busy")
            else:
                msg = _("Background Service is incompatible with Rigo")

            self._show_ok_dialog(
                None,
                escape_markup(_("Rigo")),
                escape_markup(msg))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        self._app_view_c.setup()
        self._avc.setup()
        self._nc.setup()
        self._work_view_c.setup()
        self._window.show()

    def run(self):
        """
        Run Rigo ;-)
        """
        self._welcome_box.render()
        self._change_view_state(self._current_state)
        GLib.idle_add(self._permissions_setup)

        GLib.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()
        entropy.tools.kill_threads()

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = Rigo()
    app.run()
