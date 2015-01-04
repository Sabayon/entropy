#!/usr/bin/python
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
import argparse

# entropy.i18n will pick this up
os.environ['ETP_GETTEXT_DOMAIN'] = "rigo"

import sys
from threading import Lock, Timer

sys.path.insert(0, "../lib")
sys.path.insert(1, "../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/lib")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(6, "/usr/lib/rigo")

from gi.repository import Gtk, Gdk, GLib

from rigo.paths import DATA_DIR
from rigo.enums import RigoViewStates, LocalActivityStates
from rigo.entropyapi import EntropyWebService, EntropyClient as Client
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.widgets.confupdatetreeview import ConfigUpdatesTreeView
from rigo.ui.gtk3.widgets.noticeboardtreeview import NoticeBoardTreeView
from rigo.ui.gtk3.widgets.preferencestreeview import PreferencesTreeView
from rigo.ui.gtk3.widgets.grouptreeview import GroupTreeView
from rigo.ui.gtk3.widgets.repositorytreeview import RepositoryTreeView
from rigo.ui.gtk3.widgets.notifications import NotificationBox
from rigo.ui.gtk3.controllers.applications import \
    ApplicationsViewController
from rigo.ui.gtk3.controllers.application import \
    ApplicationViewController
from rigo.ui.gtk3.controllers.confupdate import \
    ConfigUpdatesViewController
from rigo.ui.gtk3.controllers.noticeboard import \
    NoticeBoardViewController
from rigo.ui.gtk3.controllers.preference import \
    PreferenceViewController
from rigo.ui.gtk3.controllers.repository import \
    RepositoryViewController
from rigo.ui.gtk3.controllers.group import \
    GroupViewController

from rigo.ui.gtk3.controllers.notifications import \
    UpperNotificationViewController, BottomNotificationViewController
from rigo.ui.gtk3.controllers.work import \
    WorkViewController
from rigo.ui.gtk3.widgets.welcome import WelcomeBox
from rigo.ui.gtk3.models.appliststore import AppListStore
from rigo.ui.gtk3.models.confupdateliststore import ConfigUpdatesListStore
from rigo.ui.gtk3.models.noticeboardliststore import NoticeBoardListStore
from rigo.ui.gtk3.models.preferencesliststore import PreferencesListStore
from rigo.ui.gtk3.models.groupliststore import GroupListStore
from rigo.ui.gtk3.models.repositoryliststore import RepositoryListStore
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme

from rigo.utils import escape_markup
from rigo.controllers.daemon import RigoServiceController

from RigoDaemon.enums import ActivityStates as DaemonActivityStates

from entropy.const import const_debug_write, dump_signal
from entropy.misc import TimeScheduled, ParallelTask, ReadersWritersSemaphore
from entropy.i18n import _
from entropy.locks import EntropyResourcesLock

# Change the default in-RAM cache policy for repositories in order to
# save a huge amount of RAM.
from entropy.db.cache import EntropyRepositoryCachePolicies
_NONE_POL = EntropyRepositoryCachePolicies.NONE
EntropyRepositoryCachePolicies.DEFAULT_CACHE_POLICY = _NONE_POL

import entropy.tools


class Rigo(Gtk.Application):

    class RigoHandler(object):

        def __init__(self, rigo_app, rigo_service):
            self._app = rigo_app
            self._service = rigo_service

        def onDeleteWindow(self, window, event):
            # if UI is locked, do not allow to close Rigo
            if self._app.is_ui_locked() or \
                    self._service.local_activity() != LocalActivityStates.READY:
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

    def __init__(self):
        self._current_state_lock = False
        self._current_state = RigoViewStates.STATIC_VIEW_STATE
        self._state_transitions = {
            RigoViewStates.BROWSER_VIEW_STATE: (
                self._enter_browser_state,
                self._exit_browser_state),
            RigoViewStates.STATIC_VIEW_STATE: (
                self._enter_static_state,
                self._exit_static_state),
            RigoViewStates.APPLICATION_VIEW_STATE: (
                self._enter_application_state,
                self._exit_application_state),
            RigoViewStates.WORK_VIEW_STATE: (
                self._enter_work_state,
                self._exit_work_state),
            RigoViewStates.CONFUPDATES_VIEW_STATE: (
                self._enter_confupdates_state,
                self._exit_confupdates_state),
            RigoViewStates.NOTICEBOARD_VIEW_STATE: (
                self._enter_noticeboard_state,
                self._exit_noticeboard_state),
            RigoViewStates.PREFERENCES_VIEW_STATE: (
                self._enter_preferences_state,
                self._exit_preferences_state),
            RigoViewStates.REPOSITORY_VIEW_STATE: (
                self._enter_repository_state,
                self._exit_repository_state),
            RigoViewStates.GROUPS_VIEW_STATE: (
                self._enter_groups_state,
                self._exit_groups_state)
        }
        self._state_metadata = {
            RigoViewStates.BROWSER_VIEW_STATE: {
                "title": _("Search"),
                },
            RigoViewStates.STATIC_VIEW_STATE: {
                "title": _("Rigo Application Browser"),
                },
            RigoViewStates.APPLICATION_VIEW_STATE: {
                "title": _("Application"),
                },
            RigoViewStates.WORK_VIEW_STATE: {
                "title": _("Working Hard"),
                },
            RigoViewStates.CONFUPDATES_VIEW_STATE: {
                "title": _("Wake Up"),
                },
            RigoViewStates.NOTICEBOARD_VIEW_STATE: {
                "title": _("Important Stuff"),
                },
            RigoViewStates.PREFERENCES_VIEW_STATE: {
                "title": _("Breaking Stuff"),
                },
            RigoViewStates.REPOSITORY_VIEW_STATE: {
                "title": _("Repository Stuff"),
                },
            RigoViewStates.GROUPS_VIEW_STATE: {
                "title": _("Application Groups"),
                },
        }
        self._state_mutex = Lock()

        icons = get_sc_icon_theme(DATA_DIR)

        self._activity_rwsem = ReadersWritersSemaphore()

        # This relies on the fact that the installed packages repository
        # is lazily loaded (thus, schema update code is).
        self._entropy = Client()
        self._entropy_ws = EntropyWebService(self._entropy)

        preload_task = ParallelTask(self._entropy_ws.preload)
        preload_task.name = "PreloadEntropyWebService"
        preload_task.daemon = True
        preload_task.start()

        self._service = RigoServiceController(
            self, self._activity_rwsem,
            self._entropy, self._entropy_ws)

        app_handler = Rigo.RigoHandler(self, self._service)

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

        self._config_scrolled_view = self._builder.get_object(
            "configViewScrolledWindow")
        self._config_view = self._builder.get_object("configViewVbox")
        self._config_view.set_name("rigo-view")

        self._repo_scrolled_view = self._builder.get_object(
            "repoViewScrolledWindow")
        self._repo_view = self._builder.get_object("repoViewVbox")
        self._repo_view.set_name("rigo-view")

        self._notice_scrolled_view = self._builder.get_object(
            "noticeViewScrolledWindow")
        self._notice_view = self._builder.get_object("noticeViewVbox")
        self._notice_view.set_name("rigo-view")

        self._pref_scrolled_view = self._builder.get_object(
            "preferencesViewScrolledWindow")
        self._pref_view = self._builder.get_object("preferencesViewVbox")
        self._pref_view.set_name("rigo-view")

        self._group_scrolled_view = self._builder.get_object(
            "groupViewScrolledWindow")
        self._group_view = self._builder.get_object("groupViewVbox")
        self._group_view.set_name("rigo-view")

        self._search_entry = self._builder.get_object("searchEntry")
        self._search_entry_completion = self._builder.get_object(
            "searchEntryCompletion")
        self._search_entry_store = self._builder.get_object(
            "searchEntryStore")
        self._static_view = self._builder.get_object("staticViewVbox")
        self._notification = self._builder.get_object("notificationBox")
        self._bottom_notification = \
            self._builder.get_object("bottomNotificationBox")
        self._work_view = self._builder.get_object("workViewVbox")
        self._work_view.set_name("rigo-view")

        self._pref_button = self._builder.get_object(
            "prefButton")
        def _pref_button_activate(widget):
            self._change_view_state(
                RigoViewStates.PREFERENCES_VIEW_STATE)
        self._pref_button.connect(
            "clicked", _pref_button_activate)

        # Preferences model, view and controller
        self._pref_store = PreferencesListStore()
        self._view_pref = PreferencesTreeView(
            icons, PreferencesListStore.ICON_SIZE)
        self._pref_scrolled_view.add(self._view_pref)
        def _pref_queue_draw(*args):
            self._view_pref.queue_draw()
        self._pref_store.connect("redraw-request", _pref_queue_draw)
        self._pref_view_c = PreferenceViewController(
            self._pref_store, self._view_pref)

        self._app_view_c = ApplicationViewController(
            self._entropy, self._entropy_ws, self._pref_view_c,
            self._service, self._builder)

        self._view = AppTreeView(
            self._entropy, self._service, self._app_view_c, icons,
            True, AppListStore.ICON_SIZE, store=None)
        self._scrolled_view.add(self._view)
        self._view.set_scrolled_view(self._scrolled_view)

        self._app_store = AppListStore(
            self._entropy, self._entropy_ws,
            self._service, self._view, icons)
        def _queue_draw(*args):
            self._view.queue_draw()
        self._app_store.connect("redraw-request", _queue_draw)

        self._app_view_c.set_store(self._app_store)
        self._app_view_c.connect("application-show",
            self._on_application_show)

        # Configuration file updates model, view and controller
        self._config_store = ConfigUpdatesListStore()
        self._view_config = ConfigUpdatesTreeView(
            icons, ConfigUpdatesListStore.ICON_SIZE)
        self._config_scrolled_view.add(self._view_config)
        def _config_queue_draw(*args):
            self._view_config.queue_draw()
        self._config_store.connect("redraw-request", _config_queue_draw)
        self._config_view_c = ConfigUpdatesViewController(
            self._entropy, self._config_store, self._view_config)
        self._config_view_c.connect(
            "view-cleared", self._on_view_cleared)

        self._service.set_configuration_controller(self._config_view_c)

        # Repository model, view and controller
        self._repo_store = RepositoryListStore()
        self._view_repo = RepositoryTreeView(
            icons, RepositoryListStore.ICON_SIZE)
        self._repo_scrolled_view.add(self._view_repo)
        def _repo_queue_draw(*args):
            self._view_repo.queue_draw()
        self._repo_store.connect("redraw-request", _repo_queue_draw)
        self._repo_view_c = RepositoryViewController(
            self._pref_view_c, self._service, self._repo_store,
            self._view_repo)

        # NoticeBoard model, view and controller
        self._notice_store = NoticeBoardListStore()
        self._view_notice = NoticeBoardTreeView(
            icons, NoticeBoardListStore.ICON_SIZE)
        self._notice_scrolled_view.add(self._view_notice)
        def _notice_queue_draw(*args):
            self._view_notice.queue_draw()
        self._notice_store.connect("redraw-request", _notice_queue_draw)
        self._notice_view_c = NoticeBoardViewController(
            self._notice_store, self._view_notice)

        self._service.set_noticeboard_controller(self._notice_view_c)

        # Group model, view and controller
        self._group_store = GroupListStore()
        self._view_group = GroupTreeView(
            icons, GroupListStore.ICON_SIZE)
        self._group_scrolled_view.add(self._view_group)
        def _group_queue_draw(*args):
            self._view_group.queue_draw()
        self._group_store.connect("redraw-request", _group_queue_draw)
        self._group_view_c = GroupViewController(
            self._service, self._group_store,
            self._view_group, self._pref_view_c)

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

        # Force the initialization of the css provider asap.
        # This fixes a glitch with GTK 3.10
        init_sc_css_provider(
            self._window,
            settings,
            Gdk.Screen.get_default(),
            DATA_DIR)

        self._nc = UpperNotificationViewController(
            self._entropy, self._entropy_ws, self._notification)
        # Bottom NotificationBox controller.
        # Bottom notifications are only used for
        # providing Activity control to User during
        # the Activity itself.
        self._bottom_nc = BottomNotificationViewController(
            self._window, self._bottom_notification,
            self._pref_button)

        self._avc = ApplicationsViewController(
            self._activity_rwsem,
            self._entropy, self._entropy_ws,
            self._nc, self._bottom_nc, self._service,
            self._pref_view_c, icons, self._not_found_box,
            self._search_entry, self._search_entry_completion,
            self._search_entry_store, self._app_store, self._view)

        self._avc.connect("view-cleared", self._on_view_cleared)
        self._avc.connect("view-filled", self._on_view_filled)
        self._avc.connect("view-want-change", self._on_view_change)

        self._service.set_bottom_notification_controller(
            self._bottom_nc)

        self._app_view_c.set_notification_controller(self._nc)
        self._app_view_c.set_applications_controller(self._avc)

        self._config_view_c.set_notification_controller(self._nc)
        self._config_view_c.set_applications_controller(self._avc)

        self._repo_view_c.set_notification_controller(self._nc)
        self._repo_view_c.set_applications_controller(self._avc)

        self._notice_view_c.set_notification_controller(self._nc)
        self._notice_view_c.set_applications_controller(self._avc)

        self._group_view_c.set_applications_controller(self._avc)

        self._service.set_applications_controller(self._avc)
        self._service.set_application_controller(self._app_view_c)
        self._service.set_notification_controller(self._nc)

        self._service.connect("start-working", self._on_start_working)
        self._service.connect("repositories-updated",
                              self._on_repo_updated)
        self._service.connect("applications-managed",
                              self._on_applications_managed)

        self._work_view_c = WorkViewController(
            icons, self._service, self._work_view)
        self._service.set_work_controller(self._work_view_c)

        self._bottom_nc.connect("show-work-view", self._on_show_work_view)
        self._bottom_nc.connect("work-interrupt", self._on_work_interrupt)

    def is_ui_locked(self):
        """
        Return whether the UI is currently locked.
        """
        return self._current_state_lock

    def _thread_dumper(self):
        """
        If --dumper is in argv, a recurring thread dump
        function will be spawned every 30 seconds.
        """
        dumper_enable = self._nsargs.dumper
        if dumper_enable:
            task = None

            def _dumper():
                def _dump():
                    task.kill()
                    dump_signal(None, None)
                timer = Timer(10.0, _dump)
                timer.name = "MainThreadHearthbeatCheck"
                timer.daemon = True
                timer.start()
                GLib.idle_add(timer.cancel)

            task = TimeScheduled(5.0, _dumper)
            task.name = "ThreadDumper"
            task.daemon = True
            task.start()

    def _on_start_working(self, widget, state, lock):
        """
        Emitted by RigoServiceController when we're asked to
        switch to the Work View and, if lock = True, lock UI.
        """
        if lock:
            self._search_entry.set_sensitive(False)
        if state is not None:
            self._change_view_state(state, lock=lock)

    def _on_work_interrupt(self, widget):
        """
        We've been explicitly asked to interrupt the currently
        ongoing work
        """
        rc = self._show_yesno_dialog(
            self._window,
            escape_markup(_("Activity Interruption")),
            escape_markup(
                _("Are you sure you want to interrupt"
                  " the ongoing Activity? The interruption will"
                  " occur as soon as possible, potentially not"
                  " immediately.")))
        if rc == Gtk.ResponseType.NO:
            return
        self._service.interrupt_activity()

    def _on_show_work_view(self, widget):
        """
        We've been explicitly asked to switch to WORK_VIEW_STATE
        """
        self._change_view_state(RigoViewStates.WORK_VIEW_STATE,
                                _ignore_lock=True)

    def _on_repo_updated(self, widget, result, message):
        """
        Emitted by RigoServiceController telling us that
        repositories have been updated.
        """
        with self._state_mutex:
            self._current_state_lock = False
        self._search_entry.set_sensitive(True)
        if result != 0:
            msg = "<b>%s</b>: %s" % (
                _("Repositories update error"),
                message,)
            message_type = Gtk.MessageType.ERROR
        else:
            msg = _("Repositories updated <b>successfully</b>!")
            message_type = Gtk.MessageType.INFO

        box = NotificationBox(
            msg, message_type=message_type,
            context_id=RigoServiceController.NOTIFICATION_CONTEXT_ID)
        box.add_destroy_button(_("Ok, thanks"))
        self._nc.append(box)

    def _on_applications_managed(self, widget, success, local_activity):
        """
        Emitted by RigoServiceController telling us that
        enqueue application actions have been completed.
        """
        msg = "N/A"
        if not success:
            if local_activity == LocalActivityStates.MANAGING_APPLICATIONS:
                msg = "<b>%s</b>: %s" % (
                    _("Application Management Error"),
                    _("please check the management log"),)
            elif local_activity == LocalActivityStates.UPGRADING_SYSTEM:
                msg = "<b>%s</b>: %s" % (
                    _("System Upgrade Error"),
                    _("please check the upgrade log"),)
            message_type = Gtk.MessageType.ERROR
        else:
            if local_activity == LocalActivityStates.MANAGING_APPLICATIONS:
                msg = _("Applications managed <b>successfully</b>!")
            elif local_activity == LocalActivityStates.UPGRADING_SYSTEM:
                msg = _("System Upgraded <b>successfully</b>!")
            message_type = Gtk.MessageType.INFO

        box = NotificationBox(
            msg, message_type=message_type,
            context_id=RigoServiceController.NOTIFICATION_CONTEXT_ID)
        box.add_destroy_button(_("Ok, thanks"))
        box.add_button(_("Show me"), self._on_show_work_view)
        self._nc.append(box)
        self._work_view_c.deactivate_app_box()

    def _on_view_cleared(self, *args):
        self._change_view_state(RigoViewStates.STATIC_VIEW_STATE)

    def _on_view_filled(self, *args):
        self._change_view_state(RigoViewStates.BROWSER_VIEW_STATE)

    def _on_view_change(self, widget, state, payload):
        self._change_view_state(state, payload=payload)

    def _on_application_show(self, *args):
        self._change_view_state(RigoViewStates.APPLICATION_VIEW_STATE)

    def _exit_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._avc.deselect()
        self._apps_view.hide()

    def _enter_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._apps_view.show()

    def _exit_confupdates_state(self):
        """
        Action triggered when UI exits the Configuration Updates
        state (or mode).
        """
        self._config_view.hide()

    def _enter_confupdates_state(self):
        """
        Action triggered when UI enters the Configuration Updates
        state (or mode).
        """
        self._config_view.show()

    def _exit_noticeboard_state(self):
        """
        Action triggered when UI exits the NoticeBoard
        state (or mode).
        """
        self._notice_view.hide()

    def _enter_noticeboard_state(self):
        """
        Action triggered when UI enters the NoticeBoard
        state (or mode).
        """
        self._notice_view.show()

    def _exit_repository_state(self):
        """
        Action triggered when UI exits the Repository
        Management state (or mode).
        """
        self._repo_view.hide()
        self._repo_view_c.clear()

    def _enter_repository_state(self):
        """
        Action triggered when UI enters the Repository
        Management state (or mode).
        """
        self._repo_view_c.load()
        self._repo_view.show()

    def _exit_preferences_state(self):
        """
        Action triggered when UI exits the Preferences
        state (or mode).
        """
        self._pref_view.hide()

    def _enter_preferences_state(self):
        """
        Action triggered when UI enters the Preferences
        state (or mode).
        """
        self._pref_view.show()

    def _exit_groups_state(self):
        """
        Action triggered when UI exits the Groups
        state (or mode).
        """
        self._group_view.hide()

    def _enter_groups_state(self):
        """
        Action triggered when UI enters the Groups
        state (or mode).
        """
        self._group_view_c.load()
        self._group_view.show()

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

    def _change_view_state(self, state, lock=False, _ignore_lock=False,
                           payload=None):
        """
        Change Rigo Application UI state.
        You can pass a custom widget that will be shown in case
        of static view state.
        """
        with self._state_mutex:
            if self._current_state_lock and not _ignore_lock:
                const_debug_write(
                    __name__,
                    "cannot change view state, UI locked")
                return False
            txc = self._state_transitions.get(state)
            if txc is None:
                raise AttributeError("wrong view state")
            enter_st, exit_st = txc

            current_enter_st, current_exit_st = \
                self._state_transitions.get(
                    self._current_state)
            # exit from current state
            current_exit_st()
            # enter the new state
            enter_st()
            self._current_state = state
            if lock:
                self._current_state_lock = True

            state_meta = self._state_metadata[state]
            self._window.set_title(escape_markup(
                    state_meta["title"]))

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
        Show ugly Yes/No dialog window.
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

        if not self._service.service_available():
            self._show_ok_dialog(
                None,
                escape_markup(_("Rigo")),
                escape_markup(_("RigoDaemon service is not available")))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        supported_apis = self._service.supported_apis()
        daemon_api = self._service.api()
        if daemon_api not in supported_apis:
            self._show_ok_dialog(
                None,
                escape_markup(_("Rigo")),
                escape_markup(
                    _("API mismatch, please update Rigo and RigoDaemon")))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        lock = EntropyResourcesLock(output=self._entropy)
        # always execute this from the MainThread, since the lock uses TLS
        acquired = lock.try_acquire_shared()
        is_exclusive = False
        if not acquired:
            # check whether RigoDaemon is running in excluive mode
            # and ignore non-atomicity here (failing with error
            # is acceptable)
            if not self._service.exclusive():
                self._show_ok_dialog(
                    None,
                    escape_markup(_("Rigo")),
                    escape_markup(_("Another Application Manager is active")))
                entropy.tools.kill_threads()
                Gtk.main_quit()
                return
            is_exclusive = True
            # otherwise we can go ahead and handle our state later

        # check RigoDaemon, don't worry about races between Rigo Clients
        # it is fine to have multiple Rigo Clients connected. Mutual
        # exclusion is handled via Entropy Resources Lock (which is a file
        # based rwsem).
        activity = self._service.activity()
        if activity != DaemonActivityStates.AVAILABLE:
            msg = ""
            show_dialog = True

            if activity == DaemonActivityStates.NOT_AVAILABLE:
                msg = _("Background Service is currently not available")

            elif activity == DaemonActivityStates.UPDATING_REPOSITORIES:
                show_dialog = False
                task = ParallelTask(
                    self._service._update_repositories,
                    [], False, master=False)
                task.daemon = True
                task.name = "UpdateRepositoriesUnlocked"
                task.start()

            elif activity == DaemonActivityStates.MANAGING_APPLICATIONS:
                show_dialog = False
                task = ParallelTask(
                    self._service._application_request,
                    None, None, master=False)
                task.daemon = True
                task.name = "ApplicationRequestUnlocked"
                task.start()

            elif activity == DaemonActivityStates.UPGRADING_SYSTEM:
                show_dialog = False
                task = ParallelTask(
                    self._service._upgrade_system,
                    False, master=False)
                task.daemon = True
                task.name = "UpgradeSystemUnlocked"
                task.start()

            elif activity == DaemonActivityStates.INTERNAL_ROUTINES:
                msg = _("Background Service is currently busy")
            else:
                msg = _("Background Service is incompatible with Rigo")

            if show_dialog:
                self._show_ok_dialog(
                    None,
                    escape_markup(_("Rigo")),
                    escape_markup(msg))
                entropy.tools.kill_threads()
                Gtk.main_quit()
                return

        elif is_exclusive:
            msg = _("Background Service is currently unavailable")
            # no lock acquired, cannot continue the initialization
            self._show_ok_dialog(
                None,
                escape_markup(_("Rigo")),
                escape_markup(msg))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        parser = argparse.ArgumentParser(
            description=_("Rigo Application Browser"))
        parser.add_argument(
            "package", nargs='?', type=file,
            metavar="<path>", help="package path")
        parser.add_argument(
            "--install",
            metavar="<dep string>", help="install given dependency")
        parser.add_argument(
            "--remove",
            metavar="<dep string>", help="remove given dependency")
        parser.add_argument(
            "--upgrade", help="upgrade the system",
            action="store_true", default=False)
        parser.add_argument(
            "--dumper", help="enable the main thread dumper (debug)",
            action="store_true", default=False)
        parser.add_argument(
            "--debug", help="enable Entropy Library debug mode",
            action="store_true", default=False)
        try:
            self._nsargs = parser.parse_args(sys.argv[1:])
        except IOError as err:
            self._show_ok_dialog(
                None,
                escape_markup(_("Rigo")),
                escape_markup("%s" % (err,)))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        self._thread_dumper()
        self._pref_view_c.setup()
        self._group_view_c.setup()
        self._config_view_c.setup()
        self._repo_view_c.setup()
        self._notice_view_c.setup()
        self._app_view_c.setup()
        self._avc.setup()
        self._nc.setup()
        self._work_view_c.setup()
        self._service.setup(acquired)
        self._easter_eggs()
        self._window.show()
        managing = self._start_managing()
        if not managing:
            self._change_view_state(RigoViewStates.GROUPS_VIEW_STATE)
            self._service.hello()

    def _easter_eggs(self):
        """
        Moo!
        """
        msg = None
        if entropy.tools.is_st_valentine():
            msg = escape_markup(_("Happy St. Valentine <3 <3 !"))
        elif entropy.tools.is_xmas():
            msg = escape_markup(_("Merry Xmas \o/ !"))
        elif entropy.tools.is_author_bday():
            msg = escape_markup(_("Happy birthday to my authoooooor!"))
        elif entropy.tools.is_april_first():
            msg = escape_markup(_("<=|=< (this is optimistically a fish)"))
        if msg is not None:
            box = NotificationBox(
                msg, message_type=Gtk.MessageType.INFO,
                context_id="EasterEggs")
            box.add_destroy_button(_("Woot, thanks"))
            self._nc.append(box)

    def _start_managing(self):
        """
        Start managing applications passed via argv.
        """
        managing = False

        if self._nsargs.install:
            dependency = self._nsargs.install
            task = ParallelTask(
                self._avc.install, dependency)
            task.name = "AppInstall-%s" % (dependency,)
            task.daemon = True
            task.start()
            managing = True

        if self._nsargs.remove:
            dependency = self._nsargs.remove
            task = ParallelTask(
                self._avc.remove, dependency)
            task.name = "AppRemove-%s" % (dependency,)
            task.daemon = True
            task.start()
            managing = True

        if self._nsargs.package:
            path = self._nsargs.package.name
            self._nsargs.package.close() # no need, unfortunately
            task = ParallelTask(
                self._avc.install_package, path)
            task.name = "AppInstallPackage-%s" % (path,)
            task.daemon = True
            task.start()
            managing = True

        if self._nsargs.upgrade:
            task = ParallelTask(self._avc.upgrade)
            task.name = "SystemUpgrade"
            task.daemon = True
            task.start()
            managing = True

        return managing

    def run(self):
        """
        Run Rigo ;-)
        """
        self._welcome_box.render()
        self._change_view_state(self._current_state)
        GLib.idle_add(self._permissions_setup)

        Gtk.main()
        entropy.tools.kill_threads()

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = Rigo()
    app.run()
