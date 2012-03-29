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
from threading import Lock, Semaphore, Timer

import dbus
import dbus.exceptions

sys.path.insert(0, "../lib")
sys.path.insert(1, "../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/lib")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/rigo")
sys.path.insert(6, "/usr/lib/rigo")

from gi.repository import Gtk, Gdk, Gio, GLib, GObject, Vte, Pango, \
    GdkPixbuf

from rigo.paths import DATA_DIR
from rigo.enums import Icons, AppActions, RigoViewStates, \
    LocalActivityStates
from rigo.entropyapi import EntropyWebService, EntropyClient as Client
from rigo.models.application import Application
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    RepositoriesUpdateNotificationBox, UpdatesNotificationBox, \
    LoginNotificationBox, ConnectivityNotificationBox, \
    PleaseWaitNotificationBox, LicensesNotificationBox
from rigo.ui.gtk3.controllers.applications import ApplicationsViewController
from rigo.ui.gtk3.controllers.application import ApplicationViewController
from rigo.ui.gtk3.controllers.authentication import AuthenticationController
from rigo.ui.gtk3.widgets.welcome import WelcomeBox
from rigo.ui.gtk3.widgets.stars import Star
from rigo.ui.gtk3.widgets.terminal import TerminalWidget
from rigo.ui.gtk3.models.appliststore import AppListStore
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme
from rigo.utils import escape_markup, prepare_markup

from RigoDaemon.enums import ActivityStates as DaemonActivityStates, \
    AppActions as DaemonAppActions, \
    AppTransactionOutcome as DaemonAppTransactionOutcome, \
    AppTransactionStates as DaemonAppTransactionStates
from RigoDaemon.config import DbusConfig as DaemonDbusConfig, \
    PolicyActions

from entropy.const import etpConst, etpUi, const_debug_write, \
    const_debug_enabled, const_convert_to_unicode, dump_signal
from entropy.client.interfaces.repository import Repository
from entropy.misc import TimeScheduled, ParallelTask, ReadersWritersSemaphore
from entropy.i18n import _, ngettext
from entropy.output import darkgreen, brown, darkred, red, blue

import entropy.tools

class RigoServiceController(GObject.Object):

    """
    This is the Rigo Application frontend to RigoDaemon.
    Handles privileged requests on our behalf.
    """

    NOTIFICATION_CONTEXT_ID = "RigoServiceControllerContextId"

    class ServiceNotificationBox(NotificationBox):

        def __init__(self, message, message_type):
            NotificationBox.__init__(
                self, message,
                tooltip=_("Good luck!"),
                message_type=message_type,
                context_id=RigoServiceController.NOTIFICATION_CONTEXT_ID)

    class SharedLocker(object):

        """
        SharedLocker ensures that Entropy Resources
        lock and unlock operations are called once,
        avoiding reentrancy, which is a property of
        lock_resources() and unlock_resources(), even
        during concurrent access.
        """

        def __init__(self, entropy_client, locked):
            self._entropy = entropy_client
            self._locking_mutex = Lock()
            self._locked = locked

        def lock(self):
            with self._locking_mutex:
                lock = False
                if not self._locked:
                    lock = True
                    self._locked = True
            if lock:
                self._entropy.lock_resources(
                    blocking=True, shared=True)

        def unlock(self):
            with self._locking_mutex:
                unlock = False
                if self._locked:
                    unlock = True
                    self._locked = False
            if unlock:
                self._entropy.unlock_resources()

    __gsignals__ = {
        # we request to lock the whole UI wrt repo
        # interaction
        "start-working" : (GObject.SignalFlags.RUN_LAST,
                           None,
                           (GObject.TYPE_PYOBJECT,
                            GObject.TYPE_PYOBJECT),
                           ),
        # Repositories have been updated
        "repositories-updated" : (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT,
                                   GObject.TYPE_PYOBJECT,),
                                  ),
        # Application actions have been completed
        "applications-managed" : (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT,),
                                  ),
        # Application has been processed
        "application-processed" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,
                                    GObject.TYPE_PYOBJECT,
                                    GObject.TYPE_PYOBJECT,),
                                   ),
        # Application is being processed
        "application-processing" : (GObject.SignalFlags.RUN_LAST,
                                    None,
                                    (GObject.TYPE_PYOBJECT,
                                     GObject.TYPE_PYOBJECT,),
                                    ),
        "application-abort" : (GObject.SignalFlags.RUN_LAST,
                               None,
                               (GObject.TYPE_PYOBJECT,
                                GObject.TYPE_PYOBJECT,),
                               ),
    }

    DBUS_INTERFACE = DaemonDbusConfig.BUS_NAME
    DBUS_PATH = DaemonDbusConfig.OBJECT_PATH

    _OUTPUT_SIGNAL = "output"
    _REPOSITORIES_UPDATED_SIGNAL = "repositories_updated"
    _TRANSFER_OUTPUT_SIGNAL = "transfer_output"
    _PING_SIGNAL = "ping"
    _RESOURCES_UNLOCK_REQUEST_SIGNAL = "resources_unlock_request"
    _RESOURCES_LOCK_REQUEST_SIGNAL = "resources_lock_request"
    _ACTIVITY_STARTED_SIGNAL = "activity_started"
    _ACTIVITY_PROGRESS_SIGNAL = "activity_progress"
    _ACTIVITY_COMPLETED_SIGNAL = "activity_completed"
    _PROCESSING_APPLICATION_SIGNAL = "processing_application"
    _APPLICATION_PROCESSING_UPDATE = "application_processing_update"
    _APPLICATION_PROCESSED_SIGNAL = "application_processed"
    _APPLICATIONS_MANAGED_SIGNAL = "applications_managed"
    _SUPPORTED_APIS = [0]

    def __init__(self, rigo_app, activity_rwsem, auth,
                 entropy_client, entropy_ws):
        GObject.Object.__init__(self)
        self._rigo = rigo_app
        self._activity_rwsem = activity_rwsem
        self._auth = auth
        self._nc = None
        self._bottom_nc = None
        self._wc = None
        self._avc = None
        self._apc = None
        self._terminal = None
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self.__dbus_main_loop = None
        self.__system_bus = None
        self.__entropy_bus = None
        self.__entropy_bus_mutex = Lock()
        self._registered_signals = {}
        self._registered_signals_mutex = Lock()

        self._local_transactions = {}
        self._local_activity = LocalActivityStates.READY
        self._local_activity_mutex = Lock()
        self._reset_daemon_transaction_state()

        self._please_wait_box = None
        self._please_wait_mutex = Lock()

        self._application_request_serializer = Lock()
        # this controls the the busy()/unbusy()
        # atomicity.
        self._application_request_mutex = Lock()

        # threads doing repo activities must coordinate
        # with this
        self._update_repositories_mutex = Lock()

    def _reset_daemon_transaction_state(self):
        """
        Reset local daemon transaction state bits.
        """
        self._daemon_activity_progress = 0
        self._daemon_processing_application_state = None
        self._daemon_transaction_app = None
        self._daemon_transaction_app_state = None
        self._daemon_transaction_app_progress = -1

    def set_applications_controller(self, avc):
        """
        Bind ApplicationsViewController object to this class.
        """
        self._avc = avc

    def set_application_controller(self, apc):
        """
        Bind ApplicationViewController object to this class.
        """
        self._apc = apc

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

    def set_bottom_notification_controller(self, bottom_nc):
        """
        Bind a BottomNotificationViewController to this object.
        """
        self._bottom_nc = bottom_nc

    def setup(self, shared_locked):
        """
        Execute object setup once initialization phase is complete.
        This phase is comprehensive of all the set_* method calls.
        """
        if self._apc is not None:
            # connect application request events
            self._apc.connect(
                "application-request-action",
                self._on_application_request_action)

        # since we handle the lock/unlock of entropy
        # resources here, we need to know what's the
        # initial state
        self._shared_locker = self.SharedLocker(
            self._entropy, shared_locked)

    def service_available(self):
        """
        Return whether the RigoDaemon dbus service is
        available.
        """
        try:
            self._entropy_bus
            return True
        except dbus.exceptions.DBusException:
            return False

    def busy(self, local_activity):
        """
        Become busy, switch to some local activity.
        If an activity is already taking place,
        LocalActivityStates.BusyError is raised.
        If the active activity equals the requested one,
        LocalActivityStates.SameError is raised.
        """
        with self._local_activity_mutex:
            if self._local_activity == local_activity:
                raise LocalActivityStates.SameError()
            if self._local_activity != LocalActivityStates.READY:
                raise LocalActivityStates.BusyError()
            GLib.idle_add(self._bottom_nc.set_activity,
                          local_activity)
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
            GLib.idle_add(self._bottom_nc.set_activity,
                          LocalActivityStates.READY)
            self._local_activity = LocalActivityStates.READY

    def local_activity(self):
        """
        Return the current local activity (enum from LocalActivityStates)
        """
        return self._local_activity

    def local_transactions(self):
        """
        Return the current local transaction state mapping.
        """
        return self._local_transactions

    def supported_apis(self):
        """
        Return a list of supported RigoDaemon APIs.
        """
        return RigoServiceController._SUPPORTED_APIS

    @property
    def repositories_lock(self):
        """
        Return the Repositories Update Mutex object.
        This lock protects repositories access during their
        physical update.
        """
        return self._update_repositories_mutex

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

                # RigoDaemon Entropy Resources lock requests
                self.__entropy_bus.connect_to_signal(
                    self._RESOURCES_LOCK_REQUEST_SIGNAL,
                    self._resources_lock_request_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon is telling us that a new activity
                # has just begun
                self.__entropy_bus.connect_to_signal(
                    self._ACTIVITY_STARTED_SIGNAL,
                    self._activity_started_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon is telling us the activity
                # progress
                self.__entropy_bus.connect_to_signal(
                    self._ACTIVITY_PROGRESS_SIGNAL,
                    self._activity_progress_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon is telling us that an activity
                # has been completed
                self.__entropy_bus.connect_to_signal(
                    self._ACTIVITY_COMPLETED_SIGNAL,
                    self._activity_completed_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon tells us that a queue action
                # is being processed as we cycle (lol)
                self.__entropy_bus.connect_to_signal(
                    self._PROCESSING_APPLICATION_SIGNAL,
                    self._processing_application_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon tells us about an Application
                # processing status update
                self.__entropy_bus.connect_to_signal(
                    self._APPLICATION_PROCESSING_UPDATE,
                    self._application_processing_update_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon tells us that a queued app action
                # is now complete
                self.__entropy_bus.connect_to_signal(
                    self._APPLICATION_PROCESSED_SIGNAL,
                    self._application_processed_signal,
                    dbus_interface=self.DBUS_INTERFACE)

            return self.__entropy_bus

    ### GOBJECT EVENTS

    def _on_application_request_action(self, apc, app, app_action):
        """
        This event comes from ApplicationViewController notifying
        that user would like to schedule the given action for App.
        "app" is an Application object, "app_action" is an AppActions
        enum value.
        """
        const_debug_write(
            __name__,
            "_on_application_request_action: "
            "%s -> %s" % (app, app_action))
        self.application_request(app, app_action)

    ### DBUS SIGNALS

    def _processing_application_signal(self, package_id, repository_id,
                                       daemon_action, daemon_tx_state):
        const_debug_write(
            __name__,
            "_processing_application_signal: received for "
            "%d, %s, action: %s, tx state: %s" % (
                package_id, repository_id, daemon_action,
                daemon_tx_state))

        def _rate_limited_set_application(app):
            _sleep_secs = 1.0
            if self._wc is not None:
                last_t = getattr(self, "_rate_lim_set_app", 0.0)
                cur_t = time.time()
                if (abs(cur_t - last_t) < _sleep_secs):
                    # yeah, we're nazi, we sleep in the mainloop
                    time.sleep(_sleep_secs)
                setattr(self, "_rate_lim_set_app", cur_t)
                self._wc.set_application(app, daemon_action)

        # circular dep trick
        app = None
        def _redraw_callback(*args):
            if self._wc is not None:
                GLib.idle_add(
                    _rate_limited_set_application, app)

        app = Application(
            self._entropy, self._entropy_ws,
            (package_id, repository_id),
            redraw_callback=_redraw_callback)

        self._daemon_processing_application_state = daemon_tx_state
        _rate_limited_set_application(app)
        # FIXME: _daemon_transaction_app must be a set
        self._daemon_transaction_app = app
        self._daemon_transaction_app_state = None
        self._daemon_transaction_app_progress = 0

        self.emit("application-processing", app, daemon_action)

    def _application_processing_update_signal(
        self, package_id, repository_id, app_transaction_state,
        progress):
        const_debug_write(
            __name__,
            "_application_processing_update_signal: received for "
            "%i, %s, transaction_state: %s, progress: %i" % (
                package_id, repository_id,
                app_transaction_state, progress))

        app = Application(
            self._entropy, self._entropy_ws,
            (package_id, repository_id))
        # FIXME: _daemon_transaction_app must be a set
        self._daemon_transaction_app = app
        self._daemon_transaction_app_progress = progress
        self._daemon_transaction_app_state = app_transaction_state

    def _application_processed_signal(self, package_id, repository_id,
                                      daemon_action, app_outcome):
        const_debug_write(
            __name__,
            "_application_processed_signal: received for "
            "%i, %s, action: %s, outcome: %s" % (
                package_id, repository_id, daemon_action, app_outcome))

        # FIXME: _daemon_transaction_app must be a set (due to multifetch)
        self._daemon_transaction_app = None
        self._daemon_transaction_app_progress = -1
        self._daemon_transaction_app_state = None
        app = Application(
            self._entropy, self._entropy_ws,
            (package_id, repository_id),
            redraw_callback=None)
        self.emit("application-processed", app, daemon_action,
                  app_outcome)

        if app_outcome != DaemonAppTransactionOutcome.SUCCESS:
            msg = prepare_markup(_("An <b>unknown error</b> occurred"))
            if app_outcome == DaemonAppTransactionOutcome.DOWNLOAD_ERROR:
                msg = prepare_markup(_("<b>%s</b> download failed")) % (
                    app.name,)
            elif app_outcome == DaemonAppTransactionOutcome.INSTALL_ERROR:
                msg = prepare_markup(_("<b>%s</b> install failed")) % (
                    app.name,)
            elif app_outcome == DaemonAppTransactionOutcome.REMOVE_ERROR:
                msg = prepare_markup(_("<b>%s</b> removal failed")) % (
                    app.name,)
            elif app_outcome == DaemonAppTransactionOutcome.INTERNAL_ERROR:
                msg = prepare_markup(_("<b>%s</b>, internal error")) % (
                    app.name,)
            elif app_outcome == \
                DaemonAppTransactionOutcome.DEPENDENCIES_NOT_FOUND_ERROR:
                msg = prepare_markup(
                    _("<b>%s</b> dependencies not found")) % (
                        app.name,)
            elif app_outcome == \
                DaemonAppTransactionOutcome.DEPENDENCIES_COLLISION_ERROR:
                msg = prepare_markup(
                    _("<b>%s</b> dependencies collision error")) % (
                        app.name,)

            box = NotificationBox(
                msg,
                tooltip=_("An error occurred"),
                message_type=Gtk.MessageType.ERROR,
                context_id="ApplicationProcessedSignal{%s, %s}" % (
                    package_id, repository_id))
            def _show_me(*args):
                self._bottom_nc.emit("show-work-view")
            box.add_destroy_button(_("Ok, thanks"))
            box.add_button(_("Show me"), _show_me)
            self._nc.append(box)

    def _applications_managed_signal(self, success):
        """
        Signal coming from RigoDaemon notifying us that the
        MANAGING_APPLICATIONS is over.
        """
        with self._registered_signals_mutex:
            our_signals = self._registered_signals.get(
                self._APPLICATIONS_MANAGED_SIGNAL)
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
                        "_applications_managed_signal: "
                        "already consumed")
                return

        with self._application_request_mutex:
            # should be safe to block in here, because
            # the other thread can only block here when
            # we're not in busy state

            # reset progress bar, we're done with it
            if self._wc is not None:
                self._wc.reset_progress()

            local_activity = LocalActivityStates.MANAGING_APPLICATIONS
            # we don't expect to fail here, it would
            # mean programming error.
            self.unbusy(local_activity)

            # 2 -- ACTIVITY CRIT :: OFF
            self._activity_rwsem.writer_release()

            self.emit("applications-managed", success)

            const_debug_write(
                __name__,
                "_applications_managed_signal: applications-managed")

    def _repositories_updated_signal(self, result, message):
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

        # reset progress bar, we're done with it
        if self._wc is not None:
            self._wc.reset_progress()

        local_activity = LocalActivityStates.UPDATING_REPOSITORIES
        # we don't expect to fail here, it would
        # mean programming error.
        self.unbusy(local_activity)

        # 1 -- ACTIVITY CRIT :: OFF
        self._activity_rwsem.writer_release()
        self.repositories_lock.release()

        self.emit("repositories-updated",
                  result, message)

        const_debug_write(
            __name__,
            "_repositories_updated_signal: repositories-updated")

    def _output_signal(self, text, header, footer, back, importance, level,
               count_c, count_t, percent, raw):
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

        if raw:
            self._terminal.feed_child(text.replace("\n", "\r\n"))
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
        total = round(total_size, 1)

        if total > 1:
            text = "%s/%s kB @ %s/sec, %s" % (
                round(float(downloaded_size)/1024, 1),
                total,
                human_dt, time_remaining_secs)
        else:
            text = None

        self._wc.set_progress(fraction, text=text)

    def _ping_signal(self):
        """
        Need to call pong() as soon as possible to hold all Entropy
        Resources allocated by RigoDaemon.
        """
        dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).pong()

    def _resources_lock_request_signal(self, activity):
        """
        RigoDaemon is asking us to acquire a shared Entropy Resources
        lock. First we check if we have released it.
        """
        const_debug_write(
            __name__,
            "_resources_lock_request_signal: "
            "called, with remote activity: %s" % (activity,))

        def _resources_lock():
            const_debug_write(
                __name__,
                "_resources_lock_request_signal._resources_lock: "
                "enter (sleep)")

            self._shared_locker.lock()
            clear_avc = True
            if activity in (DaemonActivityStates.MANAGING_APPLICATIONS,):
                clear_avc = False
            self._release_local_resources(clear_avc=clear_avc)

            const_debug_write(
                __name__,
                "_resources_lock_request_signal._resources_lock: "
                "regained shared lock")

        task = ParallelTask(_resources_lock)
        task.name = "ResourceLockAfterRelease"
        task.daemon = True
        task.start()

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
            local_activity = self.local_activity()
            if local_activity == LocalActivityStates.READY:

                def _update_repositories():
                    accepted = self._update_repositories(
                        [], False, master=False)
                    if accepted:
                        const_debug_write(
                            __name__,
                            "_resources_unlock_request_signal: "
                            "_update_repositories accepted, unlocking")
                        self._shared_locker.unlock()

                # another client, bend over XD
                # LocalActivityStates value will be atomically
                # switched in the above thread.
                task = ParallelTask(_update_repositories)
                task.daemon = True
                task.name = "UpdateRepositoriesExternal"
                task.start()

                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal: "
                    "somebody called repo update, starting here too")

            elif local_activity == \
                    LocalActivityStates.UPDATING_REPOSITORIES:
                self._shared_locker.unlock()

                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal: "
                    "it's been us calling repositories update")
                # it's been us calling it, ignore request
                return

            else:
                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal: "
                    "not accepting RigoDaemon resources unlock request, "
                    "local activity: %s" % (local_activity,))

        elif activity == DaemonActivityStates.MANAGING_APPLICATIONS:

            local_activity = self.local_activity()
            if local_activity == LocalActivityStates.READY:

                def _application_request():
                    accepted = self._application_request(
                        None, None, master=False)
                    if accepted:
                        const_debug_write(
                            __name__,
                            "_resources_unlock_request_signal: "
                            "_application_request accepted, unlocking")
                        self._shared_locker.unlock()

                # another client, bend over XD
                # LocalActivityStates value will be atomically
                # switched in the above thread.
                task = ParallelTask(_application_request)
                task.daemon = True
                task.name = "ApplicationRequestExternal"
                task.start()

                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal: "
                    "somebody called app request, starting here too")

            elif local_activity == \
                    LocalActivityStates.MANAGING_APPLICATIONS:
                self._shared_locker.unlock()

                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal: "
                    "it's been us calling manage apps")
                # it's been us calling it, ignore request
                return

            else:
                const_debug_write(
                    __name__,
                    "_resources_unlock_request_signal 2: "
                    "not accepting RigoDaemon resources unlock request, "
                    "local activity: %s" % (local_activity,))


    def _activity_started_signal(self, activity):
        """
        RigoDaemon is telling us that the scheduled activity,
        either by us or by another Rigo, has just begun and
        that it, RigoDaemon, has now exclusive access to
        Entropy Resources.
        """
        const_debug_write(
            __name__,
            "_activity_started_signal: "
            "called, with remote activity: %s" % (activity,))

        self._reset_daemon_transaction_state()
        # reset please wait notification then
        self._please_wait(None)

    def _activity_progress_signal(self, activity, progress):
        """
        RigoDaemon is telling us the currently running activity
        progress.
        """
        const_debug_write(
            __name__,
            "_activity_progress_signal: "
            "called, with remote activity: %s, val: %i" % (
                activity, progress,))
        # update progress bar if it's not used for pushing
        # download state
        if self._daemon_processing_application_state == \
                DaemonAppTransactionStates.MANAGE:
            if self._wc is not None:
                prog = float(progress) / 100
                prog_txt = "%d %%" % (progress,)
                self._wc.set_progress(prog, text=prog_txt)

        self._daemon_activity_progress = progress

    def _activity_completed_signal(self, activity, success):
        """
        RigoDaemon is telling us that the scheduled activity,
        has been completed.
        """
        const_debug_write(
            __name__,
            "_activity_completed_signal: "
            "called, with remote activity: %s, success: %s" % (
                activity, success,))
        self._reset_daemon_transaction_state()

    ### GP PUBLIC METHODS

    def get_transaction_state(self):
        """
        Return current RigoDaemon Application transaction
        state information, if available.
        """
        app = self._daemon_transaction_app
        state = self._daemon_transaction_app_state
        progress = self._daemon_transaction_app_progress
        if app is None:
            state = None
            progress = -1
        if state is None:
            app = None
            progress = -1
        return app, state, progress

    def application_request(self, app, app_action, simulate=False):
        """
        Start Application Action (install/remove).
        """
        task = ParallelTask(self._application_request,
                            app, app_action, simulate=simulate)
        task.name = "ApplicationRequest{%s, %s}" % (
            app, app_action,)
        task.daemon = True
        task.start()

    def update_repositories(self, repositories, force):
        """
        Start Entropy Repositories Update
        """
        task = ParallelTask(self._update_repositories,
                            repositories, force)
        task.name = "UpdateRepositoriesThread"
        task.daemon = True
        task.start()

    def activity(self):
        """
        Return RigoDaemon activity states (any of RigoDaemon.ActivityStates
        values).
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).activity()

    def action_queue_length(self):
        """
        Return the current size of the RigoDaemon Application Action Queue.
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).action_queue_length()

    def action(self, app):
        """
        Return Application transaction state (RigoDaemon.AppAction enum
        value).
        """
        package_id, repository_id = app.get_details().pkg
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).action(
            package_id, repository_id)

    def exclusive(self):
        """
        Return whether RigoDaemon is running in with
        Entropy Resources acquired in exclusive mode.
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).exclusive()

    def api(self):
        """
        Return RigoDaemon API version
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).api()

    def _release_local_resources(self, clear_avc=True):
        """
        Release all the local resources (like repositories)
        that shall be used by RigoDaemon.
        For example, leaving EntropyRepository objects open
        would cause sqlite3 to deadlock.
        """
        self._entropy.rwsem().writer_acquire()
        try:
            if clear_avc:
                self._avc.clear_safe()
            self._entropy.close_repositories()
        finally:
            self._entropy.rwsem().writer_release()

    def _please_wait(self, show):
        """
        Show a Please Wait NotificationBox if show is not None,
        otherwise hide, if there.
        "show" contains the NotificationBox message.
        """
        msg = _("Waiting for <b>RigoDaemon</b>, please wait...")
        with self._please_wait_mutex:

            if show and self._please_wait_box:
                return

            if not show and not self._please_wait_box:
                return

            if not show and self._please_wait_box:
                # remove from NotificationController
                # if there
                box = self._please_wait_box
                self._please_wait_box = None
                GLib.idle_add(self._nc.remove, box)
                return

            if show and not self._please_wait_box:
                # create a new Please Wait Notification Box
                sem = Semaphore(0)

                def _make():
                    box = PleaseWaitNotificationBox(
                        msg,
                        RigoServiceController.NOTIFICATION_CONTEXT_ID)
                    self._please_wait_box = box
                    sem.release()
                    self._nc.append(box)

                GLib.idle_add(_make)
                sem.acquire()

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
        if daemon_activity == DaemonActivityStates.UPDATING_REPOSITORIES:
            action_id = PolicyActions.UPDATE_REPOSITORIES
        elif daemon_activity == DaemonActivityStates.MANAGING_APPLICATIONS:
            action_id = PolicyActions.MANAGE_APPLICATIONS
        elif daemon_activity == DaemonActivityStates.UPGRADING_SYSTEM:
            action_id = PolicyActions.UPGRADE_SYSTEM

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
        Make sure User is authorized to perform a privileged
        operation.
        """
        self._please_wait(True)
        try:
            granted = self._authorize(activity)
            if not granted:
                const_debug_write(__name__, "RigoServiceController: "
                              "_scale_up: abort")
                return False

            const_debug_write(__name__, "RigoServiceController: "
                              "_scale_up: leave")
            return True
        finally:
            self._please_wait(False)

    def _update_repositories(self, repositories, force,
                             master=True):
        """
        Ask RigoDaemon to update repositories once we're
        100% sure that the UI is locked down.
        """
        # 1 -- ACTIVITY CRIT :: ON
        self._activity_rwsem.writer_acquire() # CANBLOCK

        local_activity = LocalActivityStates.UPDATING_REPOSITORIES
        try:
            self.busy(local_activity)
            # will be unlocked when we get the signal back
        except LocalActivityStates.BusyError:
            const_debug_write(__name__, "_update_repositories: "
                              "LocalActivityStates.BusyError!")
            # 1 -- ACTIVITY CRIT :: OFF
            self._activity_rwsem.writer_release()
            return False
        except LocalActivityStates.SameError:
            const_debug_write(__name__, "_update_repositories: "
                              "LocalActivityStates.SameError!")
            # 1 -- ACTIVITY CRIT :: OFF
            self._activity_rwsem.writer_release()
            return False

        if master:
            scaled = self._scale_up(
                DaemonActivityStates.UPDATING_REPOSITORIES)
            if not scaled:
                self.unbusy(local_activity)
                # 1 -- ACTIVITY CRIT :: OFF
                self._activity_rwsem.writer_release()
                return False

        self._please_wait(True)
        accepted = self._update_repositories_unlocked(
            repositories, force, master)

        if not accepted:
            self.unbusy(local_activity)
            # 1 -- ACTIVITY CRIT :: OFF
            self._activity_rwsem.writer_release()

            def _notify():
                box = self.ServiceNotificationBox(
                    prepare_markup(
                        _("Another activity is currently in progress")),
                    Gtk.MessageType.ERROR)
                box.add_destroy_button(_("K thanks"))
                self._nc.append(box)
            GLib.idle_add(_notify)

            # unhide please wait notification
            self._please_wait(False)

            return False

        return True

    def _update_repositories_unlocked(self, repositories, force,
                                      master):
        """
        Internal method handling the actual Repositories Update
        execution.
        """
        if self._wc is not None:
            GLib.idle_add(self._wc.activate_progress_bar)
            GLib.idle_add(self._wc.deactivate_app_box)

        GLib.idle_add(self.emit, "start-working",
                      RigoViewStates.WORK_VIEW_STATE, True)

        const_debug_write(__name__, "RigoServiceController: "
                          "_update_repositories_unlocked: "
                          "start-working")

        while not self._rigo.is_ui_locked():
            const_debug_write(__name__, "RigoServiceController: "
                              "_update_repositories_unlocked: "
                              "waiting Rigo UI lock")
            time.sleep(0.5)

        const_debug_write(__name__, "RigoServiceController: "
                          "_update_repositories_unlocked: "
                          "rigo UI now locked!")

        signal_sem = Semaphore(1)

        def _repositories_updated_signal(result, message):
            if not signal_sem.acquire(False):
                # already called, no need to call again
                return
            # this is done in order to have it called
            # only once by two different code paths
            self._repositories_updated_signal(
                result, message)

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
            self._nc.clear_safe(managed=False)

        if self._terminal is not None:
            self._terminal.reset()

        self.repositories_lock.acquire()
        # not allowing other threads to mess with repos
        # will be released on repo updated signal

        self._release_local_resources()

        accepted = True
        if master:
            accepted = dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).update_repositories(repositories, force)
        else:
            # check if we need to cope with races
            self._update_repositories_signal_check(
                sig_match, signal_sem)

        return accepted

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

    def _ask_blocking_question(self, ask_meta, message, message_type):
        """
        Ask a task blocking question to User and waits for the
        answer.
        """
        box = self.ServiceNotificationBox(
            prepare_markup(message), message_type)

        def _say_yes(widget):
            ask_meta['res'] = True
            self._nc.remove(box)
            ask_meta['sem'].release()

        def _say_no(widget):
            ask_meta['res'] = False
            self._nc.remove(box)
            ask_meta['sem'].release()

        box.add_button(_("Yes, thanks"), _say_yes)
        box.add_button(_("No, sorry"), _say_no)
        self._nc.append(box)

    def _notify_blocking_message(self, sem, message, message_type):
        """
        Notify a task blocking information to User and wait for the
        acknowledgement.
        """
        box = self.ServiceNotificationBox(
            prepare_markup(message), message_type)

        def _say_kay(widget):
            self._nc.remove(box)
            if sem is not None:
                sem.release()

        box.add_button(_("Ok then"), _say_kay)
        self._nc.append(box)

    def _notify_blocking_licenses(self, ask_meta, app, license_map):
        """
        Notify licenses that have to be accepted for Application and
        block until User answers.
        """
        box = LicensesNotificationBox(app, self._entropy, license_map)

        def _license_accepted(widget, forever):
            ask_meta['forever'] = forever
            ask_meta['res'] = True
            self._nc.remove(box)
            ask_meta['sem'].release()

        def _license_declined(widget):
            ask_meta['res'] = False
            self._nc.remove(box)
            ask_meta['sem'].release()

        box.connect("accepted", _license_accepted)
        box.connect("declined", _license_declined)
        self._nc.append(box)

    def _application_request_removal_checks(self, app):
        """
        Examine Application Removal Request on behalf of
        _application_request_checks().
        """
        removable = app.is_removable()
        if not removable:
            msg = _("<b>%s</b>\nis part of the Base"
                    " System and <b>cannot</b> be removed")
            msg = msg % (app.get_markup(),)
            message_type = Gtk.MessageType.ERROR

            GLib.idle_add(
                self._notify_blocking_message,
                None, msg, message_type)

            return False

        return True

    def _accept_licenses(self, license_list):
        """
        Accept the given list of license ids.
        """
        dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).accept_licenses(
            license_list)

    def _application_request_install_checks(self, app):
        """
        Examine Application Install Request on behalf of
        _application_request_checks().
        """
        installable = True
        try:
            installable = app.is_installable()
        except Application.AcceptLicenseError as err:
            # can be installed, but licenses have to be accepted
            license_map = err.get()
            const_debug_write(
                __name__,
                "_application_request_install_checks: "
                "need to accept licenses: %s" % (license_map,))
            ask_meta = {
                'sem': Semaphore(0),
                'forever': False,
                'res': None,
            }
            GLib.idle_add(self._notify_blocking_licenses,
                          ask_meta, app, license_map)
            ask_meta['sem'].acquire()

            const_debug_write(
                __name__,
                "_application_request_install_checks: "
                "unblock, accepted:: %s, forever: %s" % (
                    ask_meta['res'], ask_meta['forever'],))

            if not ask_meta['res']:
                return False
            if ask_meta['forever']:
                self._accept_licenses(license_map.keys())
            return True

        if not installable:
            msg = _("<b>%s</b>\ncannot be installed at this time"
                    " due to <b>missing/masked</b> dependencies or"
                    " dependency <b>conflict</b>")
            msg = msg % (app.get_markup(),)
            message_type = Gtk.MessageType.ERROR

            GLib.idle_add(
                self._notify_blocking_message,
                None, msg, message_type)

            return False

        return True

    def _application_request_checks(self, app, daemon_action):
        """
        Examine Application Request before sending it to RigoDaemon.
        Specifically, check for things like system apps removal asking
        User confirmation.
        """
        if daemon_action == DaemonAppActions.REMOVE:
            accepted = self._application_request_removal_checks(app)
        else:
            accepted = self._application_request_install_checks(app)
        if not accepted:
            def _emit():
                self.emit("application-abort", app, daemon_action)
            GLib.idle_add(_emit)
        return accepted

    def _application_request_unlocked(self, app, daemon_action,
                                      master, busied, simulate):
        """
        Internal method handling the actual Application Request
        execution.
        """
        if app is not None:
            package_id, repository_id = app.get_details().pkg
        else:
            package_id, repository_id = None, None

        if busied:
            if self._wc is not None:
                GLib.idle_add(self._wc.activate_progress_bar)
                # this will be back active once we have something
                # to show
                GLib.idle_add(self._wc.deactivate_app_box)

                # Clear all the NotificationBoxes from upper area
                # we don't want people to click on them during the
                # the repo update. Kill the completely.
                if self._nc is not None:
                    self._nc.clear_safe(managed=False)

            # emit, but we don't really need to switch to
            # the work view nor locking down the UI
            GLib.idle_add(self.emit, "start-working", None, False)

            const_debug_write(__name__, "RigoServiceController: "
                              "_application_request_unlocked: "
                              "start-working")
            # don't check if UI is locked though

            signal_sem = Semaphore(1)

            def _applications_managed_signal(success):
                if not signal_sem.acquire(False):
                    # already called, no need to call again
                    return
                # this is done in order to have it called
                # only once by two different code paths
                self._applications_managed_signal(
                    success)

            with self._registered_signals_mutex:
                # connect our signal
                sig_match = self._entropy_bus.connect_to_signal(
                    self._APPLICATIONS_MANAGED_SIGNAL,
                    _applications_managed_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # and register it as a signal generated by us
                obj = self._registered_signals.setdefault(
                    self._APPLICATIONS_MANAGED_SIGNAL, [])
                obj.append(sig_match)

        self._release_local_resources(clear_avc=False)

        const_debug_write(
            __name__,
            "_application_request_unlocked, about to 'schedule'")

        accepted = True
        if master:
            accepted = dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).enqueue_application_action(
                    package_id, repository_id, daemon_action,
                    simulate)
            const_debug_write(
                __name__,
                "service enqueue_application_action, got: %s, type: %s" % (
                    accepted, type(accepted),))

            def _notify():
                queue_len = self.action_queue_length()
                msg = prepare_markup(_("<b>%s</b> action enqueued") % (
                        app.name,))
                if queue_len > 0:
                    msg += prepare_markup(ngettext(
                        ", <b>%i</b> Application enqueued so far...",
                        ", <b>%i</b> Applications enqueued so far...",
                        queue_len)) % (queue_len,)
                box = self.ServiceNotificationBox(
                    msg, Gtk.MessageType.INFO)
                self._nc.append(box, timeout=10)
            GLib.idle_add(_notify)

        else:
            self._applications_managed_signal_check(
                sig_match, signal_sem)

        return accepted

    def _applications_managed_signal_check(self, sig_match, signal_sem):
        """
        Called via _application_request_unlocked() in order to handle
        the possible race between RigoDaemon signal and the fact that
        we just lost it.
        This is only called in slave mode. When we didn't spawn the
        repositories update directly.
        """
        activity = self.activity()
        if activity == DaemonActivityStates.MANAGING_APPLICATIONS:
            return

        # lost the signal or not, we're going to force
        # the callback.
        if not signal_sem.acquire(False):
            # already called, no need to call again
            const_debug_write(
                __name__,
                "_applications_managed_signal_check: abort")
            return

        const_debug_write(
            __name__,
            "_applications_managed_signal_check: accepting")
        # Run in the main loop, to avoid calling a signal
        # callback in random threads.
        GLib.idle_add(self._applications_managed_signal,
                      True)

    def _application_request(self, app, app_action, simulate=False,
                             master=True):
        """
        Forward Application Request (install or remove) to RigoDaemon.
        Make sure there isn't any other ongoing activity.
        """
        # Need to serialize access to this method because
        # we're going to acquire several resources in a non-atomic
        # way wrt access to this method.
        with self._application_request_serializer:

            with self._application_request_mutex:
                busied = True
                # since we need to writer_acquire(), which is blocking
                # better try to allocate the local activity first
                local_activity = LocalActivityStates.MANAGING_APPLICATIONS
                try:
                    self.busy(local_activity)
                except LocalActivityStates.BusyError:
                    const_debug_write(__name__, "_application_request: "
                                      "LocalActivityStates.BusyError!")
                    # doing other stuff, cannot go ahead
                    return False
                except LocalActivityStates.SameError:
                    const_debug_write(__name__, "_application_request: "
                                      "LocalActivityStates.SameError, "
                                      "no need to acquire writer")
                    # we're already doing this activity, do not acquire
                    # activity_rwsem
                    busied = False

                if busied:
                    # 2 -- ACTIVITY CRIT :: ON
                    const_debug_write(__name__, "_application_request: "
                                      "about to acquire writer end of "
                                      "activity rwsem")
                    self._activity_rwsem.writer_acquire() # CANBLOCK

                def _unbusy():
                    if busied:
                        self.unbusy(local_activity)
                        # 2 -- ACTIVITY CRIT :: OFF
                        self._activity_rwsem.writer_release()

                if master and busied:
                    scaled = self._scale_up(
                        DaemonActivityStates.MANAGING_APPLICATIONS)
                    if not scaled:
                        _unbusy()
                        return False

                # clean terminal, make sure no crap is left there
                if self._terminal is not None:
                    self._terminal.reset()

            daemon_action = None
            if app_action == AppActions.INSTALL:
                daemon_action = DaemonAppActions.INSTALL
            elif app_action == AppActions.REMOVE:
                daemon_action = DaemonAppActions.REMOVE

            accepted = True
            do_notify = True
            if master:
                accepted = self._application_request_checks(
                    app, daemon_action)
                if not accepted:
                    do_notify = False
                const_debug_write(
                    __name__,
                    "_application_request, checks result: %s" % (
                        accepted,))

            if accepted:
                self._please_wait(True)
                accepted = self._application_request_unlocked(
                    app, daemon_action, master,
                    busied, simulate)

            if not accepted:
                with self._application_request_mutex:
                    _unbusy()

                def _notify():
                    box = self.ServiceNotificationBox(
                        prepare_markup(
                            _("Another activity is currently in progress")
                        ),
                        Gtk.MessageType.ERROR)
                    box.add_destroy_button(_("K thanks"))
                    self._nc.append(box)
                if do_notify:
                    GLib.idle_add(_notify)

            # unhide please wait notification
            self._please_wait(False)

            return accepted


class WorkViewController(GObject.Object):

    APP_IMAGE_SIZE = 48

    def __init__(self, icons, rigo_service, work_box):
        self._icons = icons
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

    def _setup_app_area(self):
        """
        Setup Application Information Area.
        """
        self._app_box = Gtk.VBox()

        hbox = Gtk.HBox()

        self._missing_icon = self._icons.load_icon(
            Icons.MISSING_APP,
            self.APP_IMAGE_SIZE, 0)

        # Image
        image_box = Gtk.VBox()
        self._app_image = Gtk.Image.new_from_pixbuf(
            self._missing_icon)

        stars_align = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        stars_align.set_padding(5, 0, 0, 0)
        self._stars = Star()
        stars_align.add(self._stars)
        self._stars.set_size_as_pixel_value(16)

        image_box.pack_start(self._app_image, False, False, 0)
        image_box.pack_start(stars_align, False, False, 0)

        hbox.pack_start(image_box, False, False, 0)

        # Action, App Name & Description
        name_align = Gtk.Alignment()
        name_align.set_padding(0, 0, 5, 0)
        name_box = Gtk.VBox()

        action_align = Gtk.Alignment()
        self._action_label = Gtk.Label("Action")
        self._action_label.set_alignment(0.0, 0.0)
        action_align.add(self._action_label)
        action_align.set_padding(0, 4, 0, 0)

        self._appname_label = Gtk.Label("App Name")
        self._appname_label.set_line_wrap(True)
        self._appname_label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._appname_label.set_alignment(0.0, 1.0)

        name_box.pack_start(action_align, False, False, 0)
        name_box.pack_start(self._appname_label, True, True, 0)
        name_align.add(name_box)

        hbox.pack_start(name_align, True, True, 5)

        self._app_box.pack_start(hbox, False, False, 5)

        return self._app_box

    def setup(self):
        """
        Initialize WorkViewController controlled resources.
        """
        self._setup_terminal_menu()

        box = self._setup_app_area()
        self._box.pack_start(box, False, False, 0)

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
        self._app_box.show_all()

    def deactivate_app_box(self):
        """
        Deactivate the Application Box showing information
        about the Application being currently handled.
        """
        self._app_box.hide()

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

    def _set_application_icon(self, app):
        """
        Set Application Icon image.
        """
        icon, cache_hit = app.get_icon()
        if icon is None:
            self._app_image.set_from_pixbuf(
                self._missing_icon)
            return

        icon_path = icon.local_document()
        if not os.path.isfile(icon_path):
            self._app_image.set_from_pixbuf(
                self._missing_icon)
            return

        try:
            img = Gtk.Image.new_from_file(icon_path)
        except GObject.GError:
            img = None

        width = self.APP_IMAGE_SIZE
        height = self.APP_IMAGE_SIZE
        img_buf = None
        if img is not None:
            img_buf = img.get_pixbuf()
        if img_buf is not None:
            w, h = img_buf.get_width(), \
                img_buf.get_height()
            if w >= 1:
                height = width * h / w

        del img_buf
        del img

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                icon_path, width, height)
            if pixbuf is not None:
                self._app_image.set_from_pixbuf(pixbuf)
            else:
                self._app_image.set_from_pixbuf(
                    self._missing_icon)
        except GObject.GError:
            self._app_image.set_from_pixbuf(
                self._missing_icon)

    def set_application(self, app, daemon_action):
        """
        Set Application information by providing its Application
        object.
        """
        msg = None
        if daemon_action == DaemonAppActions.INSTALL:
            msg = _("Installing")
        elif daemon_action == DaemonAppActions.REMOVE:
            msg = _("Removing")

        if msg is not None:
            queue_len = self._service.action_queue_length()
            more_msg = ""
            if queue_len:
                more_msg = ngettext(
                    ", and <b>%d</b> <i>more in queue</i>",
                    ", and <b>%d</b> <i>more in queue</i>",
                    queue_len)
                more_msg = prepare_markup(more_msg % (queue_len,))

            self._action_label.set_markup(
                "<big><b>%s</b>%s</big>" % (
                    escape_markup(msg),
                    more_msg,))

        self._appname_label.set_markup(
            app.get_extended_markup())

        self._set_application_icon(app)

        # rating
        stats = app.get_review_stats()
        self._stars.set_rating(stats.ratings_average)

        self.activate_app_box()
        self._app_box.queue_draw()

    def reset_progress(self):
        """
        Reset Progress Bar to intial state.
        """
        self._progress_bar.set_show_text(False)
        self._progress_bar.set_fraction(0.0)

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
        self._progress_bar.set_show_text(text is not None)

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
        self._entropy.rwsem().reader_acquire()
        try:
            def _key_func(x):
                return self._entropy.open_repository(
                    x[1]).retrieveName(x[0]).lower()
            return sorted(updates, key=_key_func)
        finally:
            self._entropy.rwsem().reader_release()

    def __calculate_updates(self):
        self._activity_rwsem.reader_acquire()
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

    def _on_upgrade(self, *args):
        """
        Callback requesting Packages Update.
        """
        # FIXME, lxnay complete
        print("On Upgrade Request Received", args)

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

        raise NotImplementedError()


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
        self._state_transactions = {
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
        }
        self._state_mutex = Lock()

        icons = get_sc_icon_theme(DATA_DIR)

        self._activity_rwsem = ReadersWritersSemaphore()
        self._entropy = Client()
        self._entropy_ws = EntropyWebService(self._entropy)
        self._auth = AuthenticationController()
        self._service = RigoServiceController(
            self, self._activity_rwsem,
            self._auth, self._entropy, self._entropy_ws)

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

        self._app_view_c = ApplicationViewController(
            self._entropy, self._entropy_ws, self._service,
            self._builder)

        self._view = AppTreeView(
            self._entropy, self._service, self._app_view_c, icons,
            True, AppListStore.ICON_SIZE, store=None)
        self._scrolled_view.add(self._view)

        self._app_store = AppListStore(
            self._entropy, self._entropy_ws,
            self._service, self._view, icons)
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
            self._search_entry, self._search_entry_completion,
            self._search_entry_store, self._app_store, self._view)

        self._avc.connect("view-cleared", self._on_view_cleared)
        self._avc.connect("view-filled", self._on_view_filled)
        self._avc.connect("view-want-change", self._on_view_change)

        self._nc = UpperNotificationViewController(
            self._activity_rwsem, self._entropy,
            self._entropy_ws, self._service,
            self._avc, self._notification)

        # Bottom NotificationBox controller.
        # Bottom notifications are only used for
        # providing Activity control to User during
        # the Activity itself.
        self._bottom_nc = BottomNotificationViewController(
            self._bottom_notification)
        self._service.set_bottom_notification_controller(
            self._bottom_nc)

        self._app_view_c.set_notification_controller(self._nc)
        self._app_view_c.set_applications_controller(self._avc)

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
        dumper_enable = "--dumper" in sys.argv
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

    def _on_applications_managed(self, widget, success):
        """
        Emitted by RigoServiceController telling us that
        enqueue application actions have been completed.
        """
        if not success:
            msg = "<b>%s</b>: %s" % (
                _("Application Management Error"),
                _("please check the install log"),)
            message_type = Gtk.MessageType.ERROR
        else:
            msg = _("Applications managed <b>successfully</b>!")
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

    def _on_view_change(self, widget, state):
        self._change_view_state(state)

    def _on_application_show(self, *args):
        self._change_view_state(RigoViewStates.APPLICATION_VIEW_STATE)

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

    def _change_view_state(self, state, lock=False, _ignore_lock=False):
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

        acquired = not self._entropy.wait_resources(
            max_lock_count=1,
            shared=True)
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

        self._thread_dumper()
        self._app_view_c.setup()
        self._avc.setup()
        self._nc.setup()
        self._work_view_c.setup()
        self._service.setup(acquired)
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
