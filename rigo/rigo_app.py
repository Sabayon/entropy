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
from threading import Lock, Semaphore

import dbus

sys.path.insert(0, "../lib")
sys.path.insert(1, "../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/lib")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/rigo")
sys.path.insert(6, "/usr/lib/rigo")

from gi.repository import Gtk, Gdk, Gio, GLib, GObject, Vte, Pango, \
    Polkit

from rigo.paths import DATA_DIR
from rigo.enums import Icons, AppActions
from rigo.entropyapi import EntropyWebService
from rigo.models.application import Application, ApplicationMetadata
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    RepositoriesUpdateNotificationBox, UpdatesNotificationBox, \
    LoginNotificationBox, ConnectivityNotificationBox
from rigo.ui.gtk3.controllers.applications import ApplicationsViewController
from rigo.ui.gtk3.controllers.application import ApplicationViewController
from rigo.ui.gtk3.widgets.welcome import WelcomeBox
from rigo.ui.gtk3.widgets.stars import ReactiveStar
from rigo.ui.gtk3.widgets.comments import CommentBox
from rigo.ui.gtk3.widgets.terminal import TerminalWidget
from rigo.ui.gtk3.widgets.images import ImageBox
from rigo.ui.gtk3.models.appliststore import AppListStore
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme
from rigo.utils import build_application_store_url, build_register_url, \
    escape_markup, prepare_markup

from RigoDaemon.enums import ActivityStates as DaemonActivityStates
from RigoDaemon.config import DbusConfig as DaemonDbusConfig

from entropy.const import etpConst, etpUi, const_debug_write, \
    const_debug_enabled, const_convert_to_unicode, const_isunicode
from entropy.client.interfaces import Client
from entropy.client.interfaces.repository import Repository
from entropy.services.client import WebService
from entropy.misc import TimeScheduled, ParallelTask, ReadersWritersSemaphore
from entropy.i18n import _, ngettext
from entropy.output import darkgreen, brown, darkred, red, blue

import entropy.tools

class RigoAuthenticationController(object):

    """
    This class handles User authentication required
    for privileged activies, like Repository updates
    and Application management.
    """

    class RigoDaemonPolicyActions:

        # PolicyKit update action
        UPDATE_REPOSITORIES = "org.sabayon.RigoDaemon.update"
        UPGRADE_SYSTEM = "org.sabayon.RigoDaemon.upgrade"
        MANAGE_APP = "org.sabayon.RigoDaemon.manage"

    def __init__(self):
        self._mainloop = GLib.MainLoop()

    def authenticate(self, action_id, authentication_callback):
        """
        Authenticate current User asking Administrator
        passwords.
        authentication_callback is the function that
        is called after the authentication procedure,
        providing one boolean argument describing the
        process result: True for authenticated, False
        for not authenticated.
        This method must be called from the MainLoop.
        """
        def _polkit_auth_callback(authority, res, loop):
            authenticated = False
            try:
                result = authority.check_authorization_finish(res)
                if result.get_is_authorized():
                    authenticated = True
                elif result.get_is_challenge():
                    authenticated = True
            except GObject.GError as err:
                const_debug_write(
                    __name__,
                    "_polkit_auth_callback: error: %s" % (err,))
            finally:
                authentication_callback(authenticated)

        # authenticated_sem will be released in the callback
        authority = Polkit.Authority.get()
        subject = Polkit.UnixProcess.new(os.getppid())
        authority.check_authorization(
                subject,
                action_id,
                None,
                Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
                None, # Gio.Cancellable()
                _polkit_auth_callback,
                self._mainloop)


class LocalActivityStates:
    (
        READY,
        UPDATING_REPOSITORIES_MASTER,
        UPDATING_REPOSITORIES_SLAVE,
        INSTALLING_APPLICATIONS,
    ) = range(4)

    class BusyError(Exception):
        """
        Cannot acknowledge a Local Activity change.
        """

    class AlreadyReadyError(Exception):
        """
        Cannot acknowledge a Local Activity change to
        "READY" state, because we're already ready.
        """

    class UnbusyFromDifferentActivity(Exception):
        """
        Unbusy request from different activity.
        """

class RigoServiceController(GObject.Object):

    """
    This is the Rigo Application frontend to Rigo Daemon.
    Handles privileged requests on our behalf.
    """

    class InconsistentDaemonState(Exception):
        """
        Raised when RigoDaemon and Rigo states are not
        coherent.
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

    DBUS_INTERFACE = DaemonDbusConfig.BUS_NAME
    DBUS_PATH = DaemonDbusConfig.OBJECT_PATH
    _OUTPUT_SIGNAL = "output"
    _REPOSITORIES_UPDATED_SIGNAL = "repositories_updated"
    _TRANSFER_OUTPUT_SIGNAL = "transfer_output"
    _EXCLUSIVE_ACQUIRED_SIGNAL = "exclusive_acquired"
    _PING_SIGNAL = "ping"
    _RESOURCES_UNLOCK_REQUEST_SIGNAL = "resources_unlock_request"

    def __init__(self, rigo_app, activity_rwsem, auth,
                 entropy_client, entropy_ws):
        GObject.Object.__init__(self)
        self._rigo = rigo_app
        self._activity_rwsem = activity_rwsem
        self._auth = auth
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
        self._local_activity = LocalActivityStates.READY
        self._local_activity_mutex = Lock()

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

    def busy(self, local_activity):
        """
        Become busy, switch to some local activity.
        If an activity is already taking place,
        LocalActivityStates.BusyError is raised.
        """
        with self._local_activity_mutex:
            if self._local_activity != LocalActivityStates.READY:
                raise LocalActivityStates.BusyError()
            self._local_activity = local_activity

    def unbusy(self, current_activity):
        """
        Exit from busy state, switch to local activity called "READY".
        If we're already out of any activity, raise
        LocalActivityStates.AlreadyReadyError()
        """
        with self._local_activity_mutex:
            if self._local_activity == LocalActivityStates.READY:
                raise LocalActivityStates.AlreadyReadyError()
            if self._local_activity != current_activity:
                raise LocalActivityStates.UnbusyFromDifferentActivity()
            self._local_activity = LocalActivityStates.READY

    def local_activity(self):
        """
        Return the current local activity (enum from LocalActivityStates)
        """
        return self._local_activity

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

                # ping/pong signaling, used to let
                # RigoDaemon release exclusive locks
                # when no client is connected
                self.__entropy_bus.connect_to_signal(
                    self._PING_SIGNAL, self._ping_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # Entropy stdout/stderr messages
                self.__entropy_bus.connect_to_signal(
                    self._OUTPUT_SIGNAL, self._output_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # Entropy UrlFetchers messages
                self.__entropy_bus.connect_to_signal(
                    self._TRANSFER_OUTPUT_SIGNAL,
                    self._transfer_output_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon Entropy Resources unlock requests
                self.__entropy_bus.connect_to_signal(
                    self._RESOURCES_UNLOCK_REQUEST_SIGNAL,
                    self._resources_unlock_request_signal,
                    dbus_interface=self.DBUS_INTERFACE)

            return self.__entropy_bus

    def _repositories_updated_signal(self, result, message,
                                     token, local_activity):
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
            else:
                # somebody already consumed this signal
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_repositories_updated_signal: "
                        "already consumed")
                return

        # Since we might sleep here, and we're in the
        # MainThread, better spawning a new thread
        # The sleep is inside _scale_down (wait on a
        # semaphore)
        def _scale_down():
            # we don't expect to fail here, it would
            # mean programming error.
            self.unbusy(local_activity)

            activity = DaemonActivityStates.UPDATING_REPOSITORIES
            slave_update = LocalActivityStates.UPDATING_REPOSITORIES_SLAVE
            if local_activity == slave_update:
                # FIXME: same??
                self._scale_down(activity, token)
            else:
                self._scale_down(activity, token)
                self._release_local_resources()

            # 1 -- ACTIVITY CRIT :: OFF
            self._activity_rwsem.writer_release()

            GLib.idle_add(self.emit, "repositories-updated")
            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "_repositories_updated_signal: repositories-updated")

        task = ParallelTask(_scale_down)
        task.name = "RepositoriesUpdatedSignalScalerDown"
        task.daemon = True
        task.start()

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

    def _ping_signal(self):
        """
        Need to call pong() as soon as possible to hold all Entropy
        Resources allocated by RigoDaemon.
        """
        dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).pong()

    def _resources_unlock_request_signal(self, activity):
        """
        RigoDaemon is asking us to release our Entropy Resources Lock.
        An ActivityStates value is provided in order to let us decide
        if we can acknowledge the request.
        """
        const_debug_write(
            __name__,
            "_resources_unlock_request_signal: "
            "called, with remote activity: %s" % (activity,))

        if activity == DaemonActivityStates.UPDATING_REPOSITORIES:
            # did we ask that or is it another client?
            if self.local_activity() == LocalActivityStates.READY:
                # another client, bend over XD
                # LocalActivityStates value will be atomically
                # switched in the above thread.
                task = ParallelTask(
                    self._update_repositories,
                    [], False,
                    master=False)
                task.daemon = True
                task.name = "UpdateRepositoriesExternal"
                task.start()
                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal: "
                    "somebody called repo update, starting here too")
            else:
                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal: "
                    "it's been us calling repositories update")
                # it's been us calling it, ignore request
                return

    def activity(self):
        """
        Return RigoDaemon activity states (any of RigoDaemon.ActivityStates
        values).
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).activity()

    def is_exclusive(self):
        """
        Return whether RigoDaemon is running in with
        Entropy Resources acquired in exclusive mode.
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).is_exclusive()

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

    def _authorize(self, daemon_activity):
        """
        Authorize privileged Activity.
        Return True for success, False for failure.
        """
        const_debug_write(__name__, "RigoServiceController: "
                          "_authorize: enter")
        auth_res = {
            'sem': Semaphore(0),
            'result': None,
            }

        def _authorized_callback(result):
            auth_res['result'] = result
            auth_res['sem'].release()

        action_id = None
        pol = RigoAuthenticationController.RigoDaemonPolicyActions
        if daemon_activity == DaemonActivityStates.UPDATING_REPOSITORIES:
            action_id = pol.UPDATE_REPOSITORIES

        if action_id is None:
            raise AttributeError("unsupported daemon activity")

        self._auth.authenticate(action_id, _authorized_callback)

        const_debug_write(__name__, "RigoServiceController: "
                          "_authorize: sleeping on sem")
        auth_res['sem'].acquire()
        const_debug_write(__name__, "RigoServiceController: "
                          "_authorize: got result: %s" % (
                auth_res['result'],))

        return auth_res['result']

    def _scale_up(self, activity):
        """
        Acquire (in blocking mode) the Entropy Resources Lock
        in exclusive mode. Scale up privileges, and ask for
        root password if not done yet.
        """
        granted = self._authorize(activity)
        if not granted:
            return False

        acquired_sem = Semaphore(0)

        const_debug_write(__name__, "RigoServiceController: "
                          "_scale_up: enter")

        def _acquirer():
            const_debug_write(__name__, "RigoServiceController: "
                              "_scale_up: acquired!")
            acquired_sem.release()

        # start the rendezvous
        sig_match = self._entropy_bus.connect_to_signal(
            self._EXCLUSIVE_ACQUIRED_SIGNAL,
            _acquirer,
            dbus_interface=self.DBUS_INTERFACE)

        accepted = dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE
            ).acquire_exclusive(activity)
        if not accepted:
            # FIXME, tell the reason to User
            return False

        self._entropy.unlock_resources()
        # FIXME: lock down UI here and show a please wait
        # state, or the user won't understand what's happening
        acquired_sem.acquire() # CANBLOCK
        sig_match.remove()

        # we successfully passed the resource to RigoDaemon
        self._connect()

        const_debug_write(__name__, "RigoServiceController: "
                          "_scale_up: leave")
        return True

    def _scale_down(self, activity, release_exclusive_token):
        """
        Release RigoDaemon Entropy Resources and regain
        control here.
        """
        acquired_sem = Semaphore(0)
        # start the rendezvous

        const_debug_write(__name__, "RigoServiceController: "
                          "_scale_down: enter, for activity: %s" % (
                activity,))

        def _acquirer(sem):
            const_debug_write(__name__, "RigoServiceController: "
                              "_scale_down._acquirer: enter")
            self._entropy.lock_resources(
                blocking=True,
                shared=True)
            const_debug_write(__name__, "RigoServiceController: "
                              "_scale_down._acquirer: leave")
            sem.release()

        task = ParallelTask(_acquirer, acquired_sem)
        task.name = "RigoDaemonResourcesReleaser"
        task.daemon = True
        task.start()

        # call this unconditionally and ignore any error.
        # multiple calls are harmless since the token
        # ensures that we actually release locks only once,
        # without the risk of running into race conditions
        accepted = dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE
            ).release_exclusive(
            activity,
            release_exclusive_token)

        # ignore accepted, unbusy() protects us from
        # releasing during other activities.
        acquired_sem.acquire()
        # back with shared lock!

        const_debug_write(__name__, "RigoServiceController: "
                          "_scale_down: leave")

    def _update_repositories(self, repositories, force,
                             master=True):
        """
        Ask RigoDaemon to update repositories once we're
        100% sure that the UI is locked down.
        """
        if master:
            local_activity = LocalActivityStates.UPDATING_REPOSITORIES_MASTER
        else:
            local_activity = LocalActivityStates.UPDATING_REPOSITORIES_SLAVE
        try:
            self.busy(local_activity)
            # will be unlocked when we get the signal back
        except LocalActivityStates.BusyError:
            # FIXME, notify user that we cannot do repo update
            const_debug_write(__name__, "_update_repositories: "
                              "LocalActivityStates.BusyError!")
            return

        if master:
            scaled = self._scale_up(
                DaemonActivityStates.UPDATING_REPOSITORIES)
            if not scaled:
                self.unbusy(local_activity)
                return
        else:
            # if we don't need to scale, just unlock
            # local resources.
            # No need to connect() because other clients have
            # already done that
            self._entropy.unlock_resources()

        self._update_repositories_unlocked(
            repositories, force, master)

    def _update_repositories_unlocked(self, repositories, force,
                                      master):
        """
        Internal method handling the actual Repositories Update
        execution.
        """
        if self._wc is not None:
            GLib.idle_add(self._wc.activate_progress_bar)
            GLib.idle_add(self._wc.deactivate_app_box)

        GLib.idle_add(self.emit, "repositories-updating",
                      Rigo.WORK_VIEW_STATE)

        if const_debug_enabled():
            const_debug_write(__name__, "RigoServiceController: "
                              "repositories-updating")

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

        if master:
            loc_activity = LocalActivityStates.UPDATING_REPOSITORIES_MASTER
        else:
            loc_activity = LocalActivityStates.UPDATING_REPOSITORIES_SLAVE

        signal_sem = Semaphore(1)

        def _repositories_updated_signal(result, message, token):
            if not signal_sem.acquire(False):
                # already called, no need to call again
                return
            # this is done in order to have it called
            # only once by two different code paths
            self._repositories_updated_signal(
                result, message, token, loc_activity)

        with self._registered_signals_mutex:
            # connect our signal
            sig_match = self._entropy_bus.connect_to_signal(
                self._REPOSITORIES_UPDATED_SIGNAL,
                _repositories_updated_signal,
                dbus_interface=self.DBUS_INTERFACE)

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

        if master:
            dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).update_repositories(repositories, force)
        else:
            # check if we need to cope with races
            self._update_repositories_signal_check(
                sig_match, signal_sem)

    def _update_repositories_signal_check(self, sig_match, signal_sem):
        """
        Called via _update_repositories_unlocked() in order to handle
        the possible race between RigoDaemon signal and the fact that
        we just lost it.
        This is only called in slave mode. When we didn't spawn the
        repositories update directly.
        """
        activity = self.activity()
        if activity == DaemonActivityStates.UPDATING_REPOSITORIES:
            return

        # lost the signal or not, we're going to force
        # the callback.
        if not signal_sem.acquire(False):
            # already called, no need to call again
            const_debug_write(
                __name__,
                "_update_repositories_signal_check: abort")
            return

        const_debug_write(
            __name__,
            "_update_repositories_signal_check: accepting")
        # Run in the main loop, to avoid calling a signal
        # callback in random threads.
        GLib.idle_add(self._repositories_updated_signal,
                      0, "", activity)

    def update_repositories(self, repositories, force):
        """
        Local method used to start Entropy repositories
        update.
        """
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
        self._service.update_repositories([], True)

    def _on_update(self, *args):
        """
        Callback requesting Repositories Update.
        """
        # FIXME, lxnay complete
        print("On Update Request Received", args)
        
        self._service.update_repositories([], True)

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
        self._auth = RigoAuthenticationController()
        self._service = RigoServiceController(
            self, self._activity_rwsem,
            self._auth, self._entropy, self._entropy_ws)

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
        self._service.set_work_controller(self._work_view_c)

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

        acquired = not self._entropy.wait_resources(
            max_lock_count=1,
            shared=True)
        is_exclusive = False
        if not acquired:
            # check whether RigoDaemon is running in excluive mode
            # and ignore non-atomicity here (failing with error
            # is acceptable)
            if not self._service.is_exclusive():
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

            elif activity == DaemonActivityStates.INSTALLING_APPLICATION:
                # FIXME, jump to WORK_VIEW and show the progress.
                msg = _("Background Service is installing Applications")
            elif activity == DaemonActivityStates.UPGRADING_SYSTEM:
                # FIXME, jump to WORK_VIEW and show the progress.
                msg = _("Background Service is updating your system")
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
