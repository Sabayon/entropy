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
import sys
import time
import codecs
from threading import Lock, Semaphore, current_thread
from collections import deque

import dbus

from gi.repository import Gtk, GLib, GObject

from rigo.enums import AppActions, RigoViewStates, \
    LocalActivityStates
from rigo.models.application import Application
from rigo.models.configupdate import ConfigUpdate
from rigo.models.noticeboard import Notice
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    PleaseWaitNotificationBox, LicensesNotificationBox, \
    OrphanedAppsNotificationBox, InstallNotificationBox, \
    RemovalNotificationBox, QueueActionNotificationBox, \
    UpdatesNotificationBox, RepositoriesUpdateNotificationBox, \
    PreservedLibsNotificationBox

from rigo.utils import prepare_markup

from RigoDaemon.enums import ActivityStates as DaemonActivityStates, \
    AppActions as DaemonAppActions, \
    AppTransactionOutcome as DaemonAppTransactionOutcome, \
    AppTransactionStates as DaemonAppTransactionStates
from RigoDaemon.config import DbusConfig as DaemonDbusConfig

from entropy.const import const_debug_write, \
    const_debug_enabled, etpConst
from entropy.locks import EntropyResourcesLock
from entropy.misc import ParallelTask
from entropy.exceptions import EntropyPackageException

from entropy.i18n import _, ngettext
from entropy.output import darkgreen, brown, darkred, red, blue, \
    MESSAGE_HEADER, ERROR_MESSAGE_HEADER, WARNING_MESSAGE_HEADER

import entropy.tools

class RigoServiceController(GObject.Object):

    """
    This is the Rigo Application frontend to RigoDaemon.
    Handles privileged requests on our behalf.
    """

    NOTIFICATION_CONTEXT_ID = "RigoServiceControllerContextId"
    ANOTHER_ACTIVITY_CONTEXT_ID = "AnotherActivityNotificationContextId"
    SYSTEM_UPGRADE_CONTEXT_ID = "SystemUpgradeContextId"
    PKG_INSTALL_CONTEXT_ID = "PackageInstallContextId"
    REPOSITORY_SETTINGS_CONTEXT_ID = "RepositoriesSettingsContextId"
    OPTIMIZE_MIRRORS_CONTEXT_ID = "MirrorsOptimizedContextId"

    class ServiceNotificationBox(NotificationBox):

        def __init__(self, message, message_type, context_id=None):
            if context_id is None:
                context_id = RigoServiceController.NOTIFICATION_CONTEXT_ID
            NotificationBox.__init__(
                self, message,
                tooltip=prepare_markup(_("Good luck!")),
                message_type=message_type,
                context_id=context_id)

    class SharedLocker(object):

        """
        SharedLocker ensures that Entropy Resources
        lock and unlock operations are called once,
        avoiding reentrancy, which is a property of
        *acquire*(), even during concurrent access.
        """

        def __init__(self, entropy_client, locked):
            self._entropy = entropy_client
            self._reslock = EntropyResourcesLock(output=self._entropy)
            self._locking_mutex = Lock()
            self._locked = locked

        def lock(self):
            with self._locking_mutex:
                lock = False
                if not self._locked:
                    lock = True
                    self._locked = True
            if lock:
                self._reslock.acquire_shared()

        def unlock(self):
            with self._locking_mutex:
                unlock = False
                if self._locked:
                    unlock = True
                    self._locked = False
            if unlock:
                self._reslock.release()

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
        # Repository settings have changed
        "repositories-settings-changed" : (GObject.SignalFlags.RUN_LAST,
                                           None,
                                           tuple(),
                                           ),
        # Application actions have been completed
        "applications-managed" : (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT,
                                   GObject.TYPE_PYOBJECT,),
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
    _ASYNC_DBUS_METHOD_TIMEOUT = 60

    _OUTPUT_SIGNAL = "output"
    _REPOSITORIES_UPDATED_SIGNAL = "repositories_updated"
    _TRANSFER_OUTPUT_SIGNAL = "transfer_output"
    _PING_SIGNAL = "ping"
    _RESOURCES_UNLOCK_REQUEST_SIGNAL = "resources_unlock_request"
    _RESOURCES_LOCK_REQUEST_SIGNAL = "resources_lock_request"
    _ACTIVITY_STARTED_SIGNAL = "activity_started"
    _ACTIVITY_PROGRESS_SIGNAL = "activity_progress"
    _ACTIVITY_COMPLETED_SIGNAL = "activity_completed"
    _APPLICATION_ENQUEUED_SIGNAL = "application_enqueued"
    _PROCESSING_APPLICATION_SIGNAL = "processing_application"
    _APPLICATION_PROCESSING_UPDATE = "application_processing_update"
    _APPLICATION_PROCESSED_SIGNAL = "application_processed"
    _APPLICATIONS_MANAGED_SIGNAL = "applications_managed"
    _UNSUPPORTED_APPLICATIONS_SIGNAL = "unsupported_applications"
    _RESTARTING_UPGRADE_SIGNAL = "restarting_system_upgrade"
    _CONFIGURATION_UPDATES_SIGNAL = "configuration_updates_available"
    _UPDATES_AVAILABLE_SIGNAL = "updates_available"
    _UNAVAILABLE_REPOSITORIES_SIGNAL = "unavailable_repositories"
    _OLD_REPOSITORIES_SIGNAL = "old_repositories"
    _NOTICEBOARDS_AVAILABLE_SIGNAL = "noticeboards_available"
    _REPOS_SETTINGS_CHANGED_SIGNAL = "repositories_settings_changed"
    _MIRRORS_OPTIMIZED_SIGNAL = "mirrors_optimized"
    _PRESERVED_LIBS_AVAILABLE_SIGNAL = "preserved_libraries_available"
    _SUPPORTED_APIS = [6, 7, 8]

    def __init__(self, rigo_app, activity_rwsem,
                 entropy_client, entropy_ws):
        GObject.Object.__init__(self)
        self._rigo = rigo_app
        self._activity_rwsem = activity_rwsem
        self._nc = None
        self._confc = None
        self._notc = None
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
        self._registered_signals = {}
        self._registered_signals_mutex = Lock()

        self._package_repositories = deque()

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

    def _dbus_to_unicode(self, dbus_string):
        """
        Convert dbus.String() to unicode object
        """
        return dbus_string.decode(etpConst['conf_encoding'])

    def set_applications_controller(self, avc):
        """
        Bind an ApplicationsViewController object to this class.
        """
        self._avc = avc

    def set_application_controller(self, apc):
        """
        Bind an ApplicationViewController object to this class.
        """
        self._apc = apc

    def set_configuration_controller(self, confc):
        """
        Bind a ConfigUpdatesViewController object to this class.
        """
        self._confc = confc

    def set_noticeboard_controller(self, notc):
        """
        Bind a NoticeBoardViewController object to this class.
        """
        self._notc = notc

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
        def _available():
            try:
                self._entropy_bus
                return True
            except dbus.exceptions.DBusException:
                return False
        return self._execute_mainloop(_available)

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
        """
        Return the Entropy D-Bus bus object.

        Always execute from the main thread to avoid races that could
        lead to deadlock.
        """
        return self._execute_mainloop(self._entropy_bus_internal_mainloop)

    def _entropy_bus_internal_mainloop(self):

        if self.__entropy_bus is not None:
            # validate, and reconnect if needed
            bus = self.__entropy_bus
            reconnect_error = "org.freedesktop.DBus.Error.ServiceUnknown"

            try:
                bus.get_dbus_method("__invalid")()
            except dbus.exceptions.DBusException as exc:
                dbus_error = exc.get_dbus_name()
                if dbus_error == reconnect_error:
                    self.__entropy_bus = None
                    const_debug_write(
                        __name__,
                        "_entropy_bus: reconnection required: %s" % (
                            exc,))

        if self.__entropy_bus is not None:
            return self.__entropy_bus

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

        # RigoDaemon tells us that there are unsupported
        # applications currently installed
        self.__entropy_bus.connect_to_signal(
            self._UNSUPPORTED_APPLICATIONS_SIGNAL,
            self._unsupported_applications_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that the currently scheduled
        # System Upgrade is being restarted due to further
        # updates being available
        self.__entropy_bus.connect_to_signal(
            self._RESTARTING_UPGRADE_SIGNAL,
            self._restarting_system_upgrade_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that a requested
        # Application action has been enqueued and
        # authorized
        self.__entropy_bus.connect_to_signal(
            self._APPLICATION_ENQUEUED_SIGNAL,
            self._application_enqueued_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that there are configuration
        # file updates available
        self.__entropy_bus.connect_to_signal(
            self._CONFIGURATION_UPDATES_SIGNAL,
            self._configuration_updates_available_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that there are app updates
        # available
        self.__entropy_bus.connect_to_signal(
            self._UPDATES_AVAILABLE_SIGNAL,
            self._updates_available_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that there are unavailable
        # repositories
        self.__entropy_bus.connect_to_signal(
            self._UNAVAILABLE_REPOSITORIES_SIGNAL,
            self._unavailable_repositories_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that there are old repositories
        self.__entropy_bus.connect_to_signal(
            self._OLD_REPOSITORIES_SIGNAL,
            self._old_repositories_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that noticeboards are available
        self.__entropy_bus.connect_to_signal(
            self._NOTICEBOARDS_AVAILABLE_SIGNAL,
            self._noticeboards_available_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that repositories settings
        # have changed
        self.__entropy_bus.connect_to_signal(
            self._REPOS_SETTINGS_CHANGED_SIGNAL,
            self._repositories_settings_changed_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon tells us that mirros have been
        # optimized
        self.__entropy_bus.connect_to_signal(
            self._MIRRORS_OPTIMIZED_SIGNAL,
            self._mirrors_optimized_signal,
            dbus_interface=self.DBUS_INTERFACE)

        # RigoDaemon talls us that there are preserved libraries
        # on the system
        try:
            self.__entropy_bus.connect_to_signal(
                self._PRESERVED_LIBS_AVAILABLE_SIGNAL,
                self._preserved_libraries_signal,
                dbus_interface=self.DBUS_INTERFACE)
        except dbus.exceptions.DBusException as exc:
            # signal may not be available, ignore.
            const_debug_write(
                __name__,
                "_entropy_bus: %s signal not available: %s" % (
                    self._PRESERVED_LIBS_AVAILABLE_SIGNAL,
                    exc,))

        return self.__entropy_bus

    def _action_to_daemon_action(self, app_action):
        """
        Convert an AppAction value to a DaemonAppAction one.
        """
        action_map = {
            AppActions.INSTALL: DaemonAppActions.INSTALL,
            AppActions.REMOVE: DaemonAppActions.REMOVE,
            AppActions.IDLE: DaemonAppActions.IDLE,
            AppActions.UPGRADE: DaemonAppActions.UPGRADE,
        }
        return action_map[app_action]

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

    def _repositories_settings_changed_signal(self, repository_ids, success):

        repository_ids = [self._dbus_to_unicode(x) for x in repository_ids]
        const_debug_write(
            __name__,
            "_repositories_settings_changed_signal, %s, success: "
            "%s" % (repository_ids, success,))

        if not success:
            # just inform user and exit
            msg = prepare_markup(
                _("Repositories Settings <b>could not</b> be changed. Sorry."))
            box = self.ServiceNotificationBox(
                msg, Gtk.MessageType.WARNING,
                context_id=self.REPOSITORY_SETTINGS_CONTEXT_ID)
            if self._nc is not None:
                self._nc.append(box, timeout=10)
            return

        def _cb():
            self._entropy._validate_repositories()

        def _notify():
            # Clear all the NotificationBoxes, in particular
            # the one listing the available updates
            if self._nc is not None:
                self._nc.clear_safe(managed=False)
            self._release_local_resources(
                clear_avc_silent=True, clear_callback=_cb) # CANBLOCK
            GLib.idle_add(self.emit, "repositories-settings-changed")
            GLib.idle_add(self.hello)

        task = ParallelTask(_notify)
        task.name = "RepositoriesChangedSignalNotifier"
        task.daemon = True
        task.start()

    def _application_enqueued_signal(self, package_id, repository_id,
                                     daemon_action):
        package_id = int(package_id)
        repository_id = self._dbus_to_unicode(repository_id)

        const_debug_write(
            __name__,
            "_application_enqueued_signal: received for "
            "%d, %s, action: %s" % (
                package_id, repository_id, daemon_action))

        queue_len = self.action_queue_length()
        if self._wc is not None:
            # also update application status
            self._wc.update_queue_information(queue_len)

        app = Application(
            self._entropy, self._entropy_ws,
            self, (package_id, repository_id))

        msg = prepare_markup(_("<b>%s</b> action enqueued") % (
                app.name,))
        if queue_len > 0:
            msg += prepare_markup(ngettext(
                    ", <b>%i</b> Application enqueued so far...",
                    ", <b>%i</b> Applications enqueued so far...",
                    queue_len)) % (queue_len,)
        box = self.ServiceNotificationBox(
            msg, Gtk.MessageType.INFO,
            context_id="ApplicationEnqueuedContextId")
        self._nc.append(box, timeout=10)

    def _processing_application_signal(self, package_id, repository_id,
                                       daemon_action, daemon_tx_state):
        package_id = int(package_id)
        repository_id = self._dbus_to_unicode(repository_id)

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
            self, (package_id, repository_id),
            redraw_callback=_redraw_callback)

        self._daemon_processing_application_state = daemon_tx_state
        _rate_limited_set_application(app)
        self._daemon_transaction_app = app
        self._daemon_transaction_app_state = None
        self._daemon_transaction_app_progress = 0

        self.emit("application-processing", app, daemon_action)

    def _application_processing_update_signal(
        self, package_id, repository_id, app_transaction_state,
        progress):
        package_id = int(package_id)
        repository_id = self._dbus_to_unicode(repository_id)

        const_debug_write(
            __name__,
            "_application_processing_update_signal: received for "
            "%i, %s, transaction_state: %s, progress: %i" % (
                package_id, repository_id,
                app_transaction_state, progress))

        app = Application(
            self._entropy, self._entropy_ws,
            self, (package_id, repository_id))
        self._daemon_transaction_app = app
        self._daemon_transaction_app_progress = progress
        self._daemon_transaction_app_state = app_transaction_state

    def _application_processed_signal(self, package_id, repository_id,
                                      daemon_action, app_outcome):
        package_id = int(package_id)
        repository_id = self._dbus_to_unicode(repository_id)

        const_debug_write(
            __name__,
            "_application_processed_signal: received for "
            "%i, %s, action: %s, outcome: %s" % (
                package_id, repository_id, daemon_action, app_outcome))

        self._daemon_transaction_app = None
        self._daemon_transaction_app_progress = -1
        self._daemon_transaction_app_state = None
        app = Application(
            self._entropy, self._entropy_ws,
            self, (package_id, repository_id),
            redraw_callback=None)

        self.emit("application-processed", app, daemon_action,
                  app_outcome)

        if app_outcome != DaemonAppTransactionOutcome.SUCCESS:
            self._notify_app_management_outcome(app, app_outcome)

    def _notify_app_management_outcome(self, app, app_outcome):
        """
        Notify User about Application Management errors.
        """
        if app is None:
            app_name = prepare_markup(_("Application"))
        else:
            app_name = app.name
        msg = prepare_markup(_("An <b>unknown error</b> occurred"))
        if app_outcome == DaemonAppTransactionOutcome.DOWNLOAD_ERROR:
            msg = prepare_markup(_("<b>%s</b> download failed")) % (
                app_name,)
        elif app_outcome == DaemonAppTransactionOutcome.INSTALL_ERROR:
            msg = prepare_markup(_("<b>%s</b> install failed")) % (
                app_name,)
        elif app_outcome == DaemonAppTransactionOutcome.REMOVE_ERROR:
            msg = prepare_markup(_("<b>%s</b> removal failed")) % (
                app_name,)
        elif app_outcome == \
                DaemonAppTransactionOutcome.PERMISSION_DENIED:
            msg = prepare_markup(_("<b>%s</b>, not authorized")) % (
                app_name,)
        elif app_outcome == DaemonAppTransactionOutcome.INTERNAL_ERROR:
            msg = prepare_markup(_("<b>%s</b>, internal error")) % (
                app_name,)
        elif app_outcome == \
            DaemonAppTransactionOutcome.DEPENDENCIES_NOT_FOUND_ERROR:
            msg = prepare_markup(
                _("<b>%s</b> dependencies not found")) % (
                    app_name,)
        elif app_outcome == \
            DaemonAppTransactionOutcome.DEPENDENCIES_COLLISION_ERROR:
            msg = prepare_markup(
                _("<b>%s</b> dependencies collision error")) % (
                    app_name,)
        elif app_outcome == \
            DaemonAppTransactionOutcome.DEPENDENCIES_NOT_REMOVABLE_ERROR:
            msg = prepare_markup(
                _("<b>%s</b> dependencies not removable error")) % (
                    app_name,)
        elif app_outcome == \
            DaemonAppTransactionOutcome.DISK_FULL_ERROR:
            msg = prepare_markup(
                _("Disk full, cannot download nor unpack Applications"))

        box = NotificationBox(
            msg,
            tooltip=prepare_markup(_("An error occurred")),
            message_type=Gtk.MessageType.ERROR,
            context_id="ApplicationOutcomeSignalError")
        def _show_me(*args):
            self._bottom_nc.emit("show-work-view")
        box.add_destroy_button(_("Ok, thanks"))
        box.add_button(_("Show me"), _show_me)
        self._nc.append(box)

    def _applications_managed_signal(self, outcome, app_log_path,
                                     local_activity):
        """
        Signal coming from RigoDaemon notifying us that the
        MANAGING_APPLICATIONS is over.
        """
        const_debug_write(
            __name__,
            "_applications_managed_signal: outcome: "
            "%s, local_activity: %s" % (
                outcome, local_activity))

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

            # This way repository in-RAM caches are reset
            # otherwise installed repository metadata becomes
            # inconsistent
            self._release_local_package_repositories()
            self._release_local_resources(clear_avc=False)

            # reset progress bar, we're done with it
            if self._wc is not None:
                self._wc.reset_progress()

            # application_processed() might have not been called
            # because the error happened earlier, thus, re-notify
            # user here.
            if outcome != DaemonAppTransactionOutcome.SUCCESS:
                self._notify_app_management_outcome(None, outcome)

            # Send Application Management notes to Terminal.
            if app_log_path:
                enc = etpConst['conf_encoding']
                app_notes = None
                try:
                    with codecs.open(app_log_path, encoding=enc) as log_f:
                        app_notes = log_f.read()
                except (IOError, OSError,) as err:
                    const_debug_write(
                        __name__,
                        "_applications_managed_signal: "
                        "cannot read app_log_path: %s" % (repr(err),))
                if app_notes is not None:
                    if len(app_notes) > 3: # chars
                        if self._terminal is not None:
                            self._terminal.reset()
                        self._output_signal(
                            app_notes, None, None, False, 0, "info",
                            0, 0, False, True)
                        if self._wc is not None:
                            self._wc.expand_terminal()

            # we don't expect to fail here, it would
            # mean programming error.
            self.unbusy(local_activity)

            # 2 -- ACTIVITY CRIT :: OFF
            self._activity_rwsem.writer_release()

            success = outcome == DaemonAppTransactionOutcome.SUCCESS
            self.emit("applications-managed", success, local_activity)

            const_debug_write(
                __name__,
                "_applications_managed_signal: applications-managed")

    def _restarting_system_upgrade_signal(self, updates_amount):
        """
        System Upgrade Activity is being restarted due to further updates
        being available. This happens when RigoDaemon processed critical
        updates during the previous activity execution.
        """
        const_debug_write(
            __name__,
            "_restarting_system_upgrade_signal: "
            "updates_amount: %s" % (updates_amount,))
        if self._nc is not None:
            msg = "%s. %s" % (
                _("<b>System Upgrade</b> Activity is being <i>restarted</i>"),
                ngettext("There is <b>%i</b> more update",
                         "There are <b>%i</b> more updates",
                         int(updates_amount)) % (updates_amount,),)
            box = self.ServiceNotificationBox(
                prepare_markup(msg), Gtk.MessageType.INFO,
                context_id=self.SYSTEM_UPGRADE_CONTEXT_ID)
            self._nc.append(box, timeout=20)

    def _updates_available_signal(self, update, update_atoms, remove,
                                  remove_atoms, one_click_update=False):
        const_debug_write(
            __name__,
            "_updates_available_signal: "
            "update: %s, remove: %s, one_click_update: %s" % (
                update, remove, one_click_update))
        if not update:
            return
        update = [(int(x), self._dbus_to_unicode(y)) for x, y \
                      in update]
        remove = [int(x) for x in remove]

        if self._nc is not None:

            with self._entropy.rwsem().reader():
                def _key_func(x):
                    return self._entropy.open_repository(
                        x[1]).retrieveName(x[0]).lower()
                update.sort(key=_key_func)

            def _on_upgrade(box):
                self._nc.remove(box)
                self.upgrade_system()

            def _on_update_show(box):
                if self._avc is not None:
                    self._avc.set_many(update)

            if not UpdatesNotificationBox.snoozed():
                box = UpdatesNotificationBox(
                    self._entropy, self._avc,
                    len(update), 0)
                box.connect("upgrade-request", _on_upgrade)
                box.connect("show-request", _on_update_show)
                self._nc.append(box)

    def _unavailable_repositories_signal(self, repositories):
        const_debug_write(
            __name__,
            "_unavailable_repositories_signal: "
            "repositories: %s" % (repositories,))

        repositories = [self._dbus_to_unicode(x) for x in repositories]
        if self._nc is not None and self._avc is not None:
            def _on_update(box):
                self._nc.remove(box)
                self.update_repositories(repositories, True)

            box = RepositoriesUpdateNotificationBox(
                self._entropy, self._avc, unavailable=repositories)
            box.connect("update-request", _on_update)
            self._nc.append(box)

    def _noticeboards_available_signal(self, notices):
        const_debug_write(
            __name__,
            "_noticeboards_available_signal: called")
        if self._nc is not None and self._notc is not None:
            notice_boards = []
            for repository, notice_id, guid, link, title, desc, date in notices:
                data = {
                    'guid': self._dbus_to_unicode(guid),
                    'link': self._dbus_to_unicode(link),
                    'title': self._dbus_to_unicode(title),
                    'description': self._dbus_to_unicode(desc),
                    'pubDate': self._dbus_to_unicode(date)
                }
                nb = Notice(repository, notice_id, data)
                notice_boards.append(nb)
            if notice_boards:
                self._notc.notify_notices(notice_boards)

    def _old_repositories_signal(self):
        const_debug_write(
            __name__,
            "_old_repositories_signal: called")
        if self._nc is not None and self._avc is not None:
            def _on_update(box):
                self._nc.remove(box)
                self.update_repositories([], False)

            box = RepositoriesUpdateNotificationBox(
                self._entropy, self._avc)
            box.connect("update-request", _on_update)
            self._nc.append(box)

    def _configuration_updates_available_signal(self, updates):
        const_debug_write(
            __name__,
            "_configuration_updates_available_signal: "
            "updates: %s" % (updates,))

        if self._confc is not None and self._nc is not None:

            with self._entropy.rwsem().reader():
                inst_repo = self._entropy.installed_repository()
                repository_id = inst_repo.repository_id()

            config_updates = []
            for root, source, dest, pkg_ids, auto in updates:
                apps = []
                for package_id in pkg_ids:
                    app = Application(
                        self._entropy, self._entropy_ws,
                        self, (int(package_id), repository_id))
                    apps.append(app)
                meta = {
                    'root': self._dbus_to_unicode(root),
                    'destination': self._dbus_to_unicode(dest),
                    'automerge': bool(auto),
                    'apps': apps,
                }
                cu = ConfigUpdate(source, meta, self, self._nc)
                config_updates.append(cu)
            self._confc.notify_updates(config_updates)

    def _unsupported_applications_signal(self, manual_package_ids,
                                         package_ids):
        const_debug_write(
            __name__,
            "_unsupported_applications_signal: manual: "
            "%s, normal: %s" % (
                manual_package_ids, package_ids))

        with self._entropy.rwsem().reader():
            inst_repo = self._entropy.installed_repository()
            repository_id = inst_repo.repository_id()

        if manual_package_ids or package_ids:
            manual_apps = []
            apps = []
            list_objs = [(manual_package_ids, manual_apps),
                         (package_ids, apps)]
            for source_list, app_list in list_objs:
                for package_id in source_list:
                    app = Application(
                        self._entropy, self._entropy_ws,
                        self, (package_id, repository_id))
                    app_list.append(app)

            if self._nc is not None:
                box = OrphanedAppsNotificationBox(
                    self._apc, self, self._entropy, self._entropy_ws,
                    manual_apps, apps)
                self._nc.append(box)

    def _repositories_updated_signal(self, result, message):
        """
        Signal coming from RigoDaemon notifying us that repositories have
        been updated.
        """
        const_debug_write(
            __name__,
            "_repositories_updated_signal: "
            "result: %s, message: %s" % (result, message,))
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

        # revalidate all the repositories
        # so that Entropy.repositories() and other internal
        # metadata is consistent with the newly available
        # repositories.
        with self._entropy.rwsem().writer():
            self._entropy._validate_repositories()

        local_activity = LocalActivityStates.UPDATING_REPOSITORIES
        # we don't expect to fail here, it would
        # mean programming error.
        self.unbusy(local_activity)

        # 1 -- ACTIVITY CRIT :: OFF
        self._activity_rwsem.writer_release()
        self.repositories_lock.release()

        self.emit("repositories-updated",
                  result, message)

        # send hello again in order to receive new update info
        self.hello()

        const_debug_write(
            __name__,
            "_repositories_updated_signal: repositories-updated")

    def _mirrors_optimized_signal(self, repository_ids, optimized):

        repository_ids = [self._dbus_to_unicode(x) for x in \
                              repository_ids]

        const_debug_write(
            __name__,
            "_mirrors_optimized_signal: received for "
            "%s, optimized: %s" % (repository_ids, optimized,))

        if optimized:
            msg = prepare_markup(
                _("Congratulations, mirrors have been <b>optimized</b>!"))
            msg_type = Gtk.MessageType.INFO
        else:
            msg = prepare_markup(
                _("Ouch, mirrors <b>not optimized</b>, sorry!"))
            msg_type = Gtk.MessageType.WARNING

        box = self.ServiceNotificationBox(
            msg, msg_type,
            context_id=self.OPTIMIZE_MIRRORS_CONTEXT_ID)
        self._nc.append(box, timeout=30)

    def _preserved_libraries_signal(self, preserved):
        """
        RigoDaemon is signaling that there are preserved libraries on the
        system.
        """
        if self._nc is not None:

            def _on_upgrade(box):
                self._nc.remove(box)
                self.upgrade_system()

            box = PreservedLibsNotificationBox(preserved)
            box.connect("upgrade-request", _on_upgrade)
            self._nc.append(box)

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
        hdr = MESSAGE_HEADER
        if level == "warning":
            color_func = brown
            hdr = WARNING_MESSAGE_HEADER
        elif level == "error":
            color_func = darkred
            hdr = ERROR_MESSAGE_HEADER

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
            msg = "\r" + color_func(hdr) + " " + header + count_str + text \
                + footer
        else:
            msg = "\r" + color_func(hdr) + " " + header + count_str + text \
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
                round(float(downloaded_size)/1000, 1),
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

            # always execute this from the MainThread, since the lock uses TLS
            self._execute_mainloop(self._shared_locker.lock)
            clear_avc = True
            if activity in (
                DaemonActivityStates.MANAGING_APPLICATIONS,
                DaemonActivityStates.UPGRADING_SYSTEM,):
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
                    self._release_local_resources()
                    accepted = self._update_repositories(
                        [], False, master=False)
                    if accepted:
                        const_debug_write(
                            __name__,
                            "_resources_unlock_request_signal: "
                            "_update_repositories accepted, unlocking")
                        # always execute this from the MainThread,
                        # since the lock uses TLS
                        self._execute_mainloop(self._shared_locker.unlock)

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

                def _unlocker():
                    self._release_local_resources() # CANBLOCK
                    # always execute this from the MainThread,
                    # since the lock uses TLS
                    self._execute_mainloop(self._shared_locker.unlock)

                task = ParallelTask(_unlocker)
                task.daemon = True
                task.name = "UpdateRepositoriesInternal"
                task.start()

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

    def package_install_request(self, package_path, simulate=False):
        """
        Start Application Install Action for package file.
        """
        task = ParallelTask(self._package_install_request,
                            package_path, simulate=simulate)
        task.name = "PackageInstallRequest{%s, %s}" % (
            package_path, simulate,)
        task.daemon = True
        task.start()

    def upgrade_system(self, simulate=False):
        """
        Start a System Upgrade.
        """
        task = ParallelTask(self._upgrade_system,
                            simulate=simulate)
        task.name = "UpgradeSystem{simulate=%s}" % (
            simulate,)
        task.daemon = True
        task.start()

    def update_repositories(self, repositories, force):
        """
        Start Entropy Repositories Update
        """
        # Un-snooze repositories update notification box.
        # We will be back nagging the user about possible
        # package updates.
        UpdatesNotificationBox.unsnooze()
        task = ParallelTask(self._update_repositories,
                            repositories, force)
        task.name = "UpdateRepositoriesThread"
        task.daemon = True
        task.start()

    def optimize_mirrors(self, repository_ids):
        """
        Request mirror list optimization (basically
        sorting per throughput) for the given
        Repositories.
        """
        if self.api() < 7:
            # ignore request, RigoDaemon is too old
            return

        def _optimize():
            accepted = dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).optimize_mirrors(repository_ids)
            if accepted:
                msg = prepare_markup(
                    _("Mirrors will be optimized in <b>background</b>..."))
                msg_type = Gtk.MessageType.INFO
            else:
                msg = prepare_markup(
                    _("Mirrors optimization <b>not available</b> at this time"))
                msg_type = Gtk.MessageType.WARNING
            box = self.ServiceNotificationBox(
                msg, msg_type,
                context_id=self.OPTIMIZE_MIRRORS_CONTEXT_ID)
            self._nc.append(box, timeout=30)
            return accepted

        return self._execute_mainloop(_optimize)

    def configuration_updates(self):
        """
        Request pending Configuration File Updates.
        """
        def _config():
            dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).configuration_updates()
        return self._execute_mainloop(_config)

    def noticeboards(self):
        """
        Request Repositories NoticeBoards.
        """
        def _notice():
            dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).noticeboards()
        return self._execute_mainloop(_notice)

    def groups(self):
        """
        Return the Entropy Package Groups object.
        """
        with self._entropy.rwsem().reader():
            return self._entropy.get_package_groups()

    def list_repositories(self):
        """
        Return a list of Available Repositories, ordered by
        repository_id. Each list item is a tuple composed by
        (repository_id, description, enabled/disabled)
        """
        with self._entropy.rwsem().reader():

            settings = self._entropy.Settings()
            repo_data = settings['repositories']
            available = repo_data['available']
            excluded = repo_data['excluded']

            repositories = []
            for repository_id, data in available.items():
                repositories.append(
                    (repository_id, data['description'], True))
            for repository_id, data in excluded.items():
                repositories.append(
                    (repository_id, data['description'], False))

            repositories.sort(key=lambda x: x[0])
            return repositories

    def enable_repository(self, repository_id):
        """
        Enable the given Repository (if disabled).
        Return True if action has been accepted by RigoDaemon,
        False otherwise.
        """
        def _execute():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).enable_repository(
                    repository_id)
        return self._execute_mainloop(_execute)

    def disable_repository(self, repository_id):
        """
        Disable the given Repository (if disabled).
        Return True if action has been accepted by RigoDaemon,
        False otherwise.
        """
        def _execute():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).disable_repository(
                    repository_id)
        return self._execute_mainloop(_execute)

    def rename_repository(self, from_repository_id, to_repository_id):
        """
        Rename a Repository.
        Return True if action has been accepted by RigoDaemon,
        False otherwise.
        """
        def _execute():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).rename_repository(
                    from_repository_id, to_repository_id)
        return self._execute_mainloop(_execute)

    def merge_configuration(self, source, reply_handler=None,
                            error_handler=None):
        """
        Move configuration file from source path over to
        destination, keeping destination path permissions.
        """
        def _merge():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).merge_configuration(
                    source,
                    reply_handler=reply_handler,
                    error_handler=error_handler,
                    timeout=self._ASYNC_DBUS_METHOD_TIMEOUT)
        return self._execute_mainloop(_merge)

    def diff_configuration(self, source, reply_handler=None,
                           error_handler=None):
        """
        Generate a diff between destination -> source file paths and
        return a path containing the output to caller. If diff cannot
        be run, return empty string.
        """
        def _diff():
            outcome = dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).diff_configuration(
                    source, reply_handler=reply_handler,
                    error_handler=error_handler,
                    timeout=self._ASYNC_DBUS_METHOD_TIMEOUT)
            if outcome is not None:
                return self._dbus_to_unicode(outcome)
        return self._execute_mainloop(_diff)

    def view_configuration_destination(self, source, reply_handler=None,
                                       error_handler=None):
        """
        Copy configuration destination file to a temporary path featuring
        caller ownership. If file cannot be copied, empty string is
        returned.
        """
        def _view():
            outcome = dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).view_configuration_destination(
                    source, reply_handler=reply_handler,
                    error_handler=error_handler,
                    timeout=self._ASYNC_DBUS_METHOD_TIMEOUT)
            if outcome is not None:
                return self._dbus_to_unicode(outcome)
        return self._execute_mainloop(_view)

    def view_configuration_source(self, source, reply_handler=None,
                                  error_handler=None):
        """
        Copy configuration source file to a temporary path featuring
        caller ownership. If file cannot be copied, empty string is
        returned.
        """
        def _view():
            outcome = dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).view_configuration_source(
                    source, reply_handler=reply_handler,
                    error_handler=error_handler,
                    timeout=self._ASYNC_DBUS_METHOD_TIMEOUT)
            if outcome is not None:
                return self._dbus_to_unicode(outcome)
        return self._execute_mainloop(_view)

    def save_configuration_source(self, source, path, reply_handler=None,
                                  error_handler=None):
        """
        Save a new proposed source configuration file to the given
        source file, if exists.
        """
        def _save():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).save_configuration_source(
                    source, path, reply_handler=reply_handler,
                    error_handler=error_handler,
                    timeout=self._ASYNC_DBUS_METHOD_TIMEOUT)
        return self._execute_mainloop(_save)

    def discard_configuration(self, source, reply_handler=None,
                              error_handler=None):
        """
        Remove configuration file from source path.
        """
        def _discard():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).discard_configuration(
                    source, reply_handler=reply_handler,
                    error_handler=error_handler,
                    timeout=self._ASYNC_DBUS_METHOD_TIMEOUT)
        return self._execute_mainloop(_discard)

    def reload_configuration_updates(self):
        """
        Load a new ConfigurationFiles object.
        """
        def _reload():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE
                ).reload_configuration_updates()
        self._execute_mainloop(_reload)

    def interrupt_activity(self):
        """
        Interrupt any RigoDaemon activity.
        """
        def _interrupt():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).interrupt_activity()
        return self._execute_mainloop(_interrupt)

    def activity(self):
        """
        Return RigoDaemon activity states (any of RigoDaemon.ActivityStates
        values).
        """
        def _activity():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).activity()
        return self._execute_mainloop(_activity)

    def action_queue_length(self):
        """
        Return the current size of the RigoDaemon Application Action Queue.
        """
        def _action_queue_length():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).action_queue_length()
        return self._execute_mainloop(_action_queue_length)

    def action_queue_items(self):
        """
        Return the list of Application objects that are currently processed by
        RigoDaemon. This is a kind of instant snapshot of what's going on there.
        """
        def _action_queue_items():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).action_queue_items()
        items = self._execute_mainloop(_action_queue_items)

        apps = []
        for item in items:
            pkg_id, r_id, path, daemon_action, simulate, children = item
            is_upgrade = False
            if daemon_action == DaemonAppActions.UPGRADE:
                # special case, system is upgrading, append
                # the children list
                is_upgrade = True

            app_children = None
            if children:
                app_children = []
            for _pkg_id, _r_id, _action in children:
                _pkg_id = int(_pkg_id)
                _r_id = self._dbus_to_unicode(_r_id)
                app = Application(
                    self._entropy, self._entropy_ws,
                    self, (_pkg_id, _r_id))
                if is_upgrade:
                    apps.append(app)
                else:
                    app_children.append(app)

            if is_upgrade:
                continue

            pkg_id = int(pkg_id)
            r_id = self._dbus_to_unicode(r_id)
            if path:
                path = self._dbus_to_unicode(path)
            else:
                path = None
            app = Application(self._entropy, self._entropy_ws,
                              self, (pkg_id, r_id),
                              package_path=path,
                              children=app_children)
            apps.append(app)
        return apps

    def action(self, app):
        """
        Return Application transaction state (RigoDaemon.AppAction enum
        value).
        """
        package_id, repository_id = app.get_details().pkg
        def _action():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).action(
                package_id, repository_id)
        return self._execute_mainloop(_action)

    def exclusive(self):
        """
        Return whether RigoDaemon is running in with
        Entropy Resources acquired in exclusive mode.
        """
        def _exclusive():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).exclusive()
        return self._execute_mainloop(_exclusive)

    def api(self):
        """
        Return RigoDaemon API version
        """
        def _api():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).api()
        return self._execute_mainloop(_api)

    def hello(self):
        """
        Say hello to RigoDaemon. This causes the sending of
        several welcome signals, such as updates notification.
        """
        def _hello():
            return dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).hello()
        self._execute_mainloop(_hello)

    def _execute_mainloop(self, function, *args, **kwargs):
        """
        Execute a function inside the MainLoop and return
        the result to the caller.
        """
        if current_thread().name == "MainThread":
            return function(*args, **kwargs)

        sem_data = {
            'sem': Semaphore(0),
            'res': None,
            'exc': None,
        }
        def _wrapper():
            try:
                sem_data['res'] = function(*args, **kwargs)
            except Exception as exc:
                sem_data['exc'] = exc
            finally:
                sem_data['sem'].release()
        GLib.idle_add(_wrapper)
        sem_data['sem'].acquire()
        if sem_data['exc'] is not None:
            raise sem_data['exc']
        return sem_data['res']

    def _release_local_package_repositories(self):
        """
        Release all the local package file repositories.
        """
        with self._entropy.rwsem().writer():
            while True:
                try:
                    repository_id = self._package_repositories.popleft()
                except IndexError:
                    break
                self._entropy.remove_repository(
                    repository_id)

    def _release_local_resources(self, clear_avc=True,
                                 clear_avc_silent=False,
                                 clear_callback=None):
        """
        Release all the local resources (like repositories)
        that shall be used by RigoDaemon.
        For example, leaving EntropyRepository objects open
        would cause sqlite3 to deadlock.
        """
        with self._entropy.rwsem().writer():

            if clear_avc and self._avc is not None:
                if clear_avc_silent:
                    self._avc.clear_silent_safe()
                else:
                    self._avc.clear_safe()
            self._entropy.close_repositories()
            if clear_callback is not None:
                clear_callback()

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
                    Gtk.MessageType.ERROR,
                    context_id=self.ANOTHER_ACTIVITY_CONTEXT_ID)
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
            sig_match = self._execute_mainloop(
                self._entropy_bus.connect_to_signal,
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

        accepted = True
        if master:
            def _enqueue():
                return dbus.Interface(
                    self._entropy_bus,
                    dbus_interface=self.DBUS_INTERFACE
                    ).update_repositories(repositories, force)
            accepted = self._execute_mainloop(_enqueue)

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
            prepare_markup(message), message_type,
            context_id="BlockingQuestion-%d" % (id(ask_meta),))

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
            prepare_markup(message), message_type,
            context_id="BlockingMessage-%d" % (id(sem),))

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

    def _notify_blocking_install(self, ask_meta, app, install):
        """
        Ask User to acknowledge the proposed install queue.
        """
        box = InstallNotificationBox(
            self._apc, self._avc, app, self._entropy,
            self._entropy_ws, self, install)

        def _accepted(widget):
            ask_meta['res'] = True
            self._nc.remove(box)
            ask_meta['sem'].release()

        def _declined(widget):
            ask_meta['res'] = False
            self._nc.remove(box)
            ask_meta['sem'].release()

        box.connect("accepted", _accepted)
        box.connect("declined", _declined)
        self._nc.append(box)

    def _notify_blocking_removal(self, ask_meta, app, remove):
        """
        Ask User to acknowledge the proposed removal queue.
        """
        box = RemovalNotificationBox(
            self._apc, self._avc, app, self._entropy,
            self._entropy_ws, self, remove)

        def _accepted(widget):
            ask_meta['res'] = True
            self._nc.remove(box)
            ask_meta['sem'].release()

        def _declined(widget):
            ask_meta['res'] = False
            self._nc.remove(box)
            ask_meta['sem'].release()

        box.connect("accepted", _accepted)
        box.connect("declined", _declined)
        self._nc.append(box)

    def _application_request_removal_checks(self, app):
        """
        Examine Application Removal Request on behalf of
        _application_request_checks().
        """
        queue = app.get_removal_queue()
        if queue is None:
            msg = _("<b>%s</b>\nis part of the Base"
                    " System and <b>cannot</b> be removed")
            msg = msg % (app.get_markup(),)
            message_type = Gtk.MessageType.ERROR

            GLib.idle_add(
                self._notify_blocking_message,
                None, msg, message_type)

            return False

        if len(queue) > 1:
            const_debug_write(
                __name__,
                "_application_request_removal_checks: "
                "need to ack queue: %s" % (queue,))
            ask_meta = {
                'sem': Semaphore(0),
                'res': None,
            }
            GLib.idle_add(self._notify_blocking_removal,
                          ask_meta, app, queue)
            ask_meta['sem'].acquire()

            const_debug_write(
                __name__,
                "_application_request_removal_checks: "
                "queue acked?: %s" % (ask_meta['res'],))

            if not ask_meta['res']:
                return False

        return True

    def _accept_licenses(self, license_list):
        """
        Accept the given list of license ids.
        """
        def _accept():
            dbus.Interface(
                self._entropy_bus,
                dbus_interface=self.DBUS_INTERFACE).accept_licenses(
                license_list)
        self._execute_mainloop(_accept)

    def _application_request_install_checks(self, app):
        """
        Examine Application Install Request on behalf of
        _application_request_checks().
        """
        queues = app.get_install_queue()
        if queues is None:
            msg = prepare_markup(
                _("<b>%s</b>\ncannot be installed at this time"
                    " due to <b>missing/masked</b> dependencies or"
                    " dependency <b>conflict</b>"))
            msg = msg % (app.get_markup(),)
            message_type = Gtk.MessageType.ERROR

            GLib.idle_add(
                self._notify_blocking_message,
                None, msg, message_type)
            return False

        install, conflicting_apps = queues

        if len(install) > 1:
            const_debug_write(
                __name__,
                "_application_request_install_checks: "
                "need to ack queue: %s" % (install,))
            ask_meta = {
                'sem': Semaphore(0),
                'res': None,
            }
            GLib.idle_add(self._notify_blocking_install,
                          ask_meta, app, install)
            ask_meta['sem'].acquire()

            const_debug_write(
                __name__,
                "_application_request_install_checks: "
                "queue acked?: %s" % (ask_meta['res'],))

            if not ask_meta['res']:
                return False

        license_map = app.accept_licenses(install)
        if license_map:
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

        if conflicting_apps:
            msg = prepare_markup(
                _("Installing <b>%s</b> would cause the removal"
                  " of the following Applications: %s"))
            msg = msg % (
                app.name,
                ", ".join(
                    ["<b>" + x.name + "</b>" for x in conflicting_apps]),)
            message_type = Gtk.MessageType.WARNING

            ask_meta = {
                'res': None,
                'sem': Semaphore(0),
            }
            GLib.idle_add(self._ask_blocking_question, ask_meta,
                          msg, message_type)
            ask_meta['sem'].acquire() # CANBLOCK
            if not ask_meta['res']:
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
            package_path = app.path
        else:
            package_id, repository_id = None, None
            package_path = None
        if package_path is None:
            package_path = ""

        sig_match = None
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

            def _applications_managed_signal(outcome, app_log_path):
                if not signal_sem.acquire(False):
                    # already called, no need to call again
                    return
                # this is done in order to have it called
                # only once by two different code paths
                self._applications_managed_signal(
                    outcome, app_log_path,
                    LocalActivityStates.MANAGING_APPLICATIONS)

            with self._registered_signals_mutex:
                # connect our signal
                sig_match = self._execute_mainloop(
                    self._entropy_bus.connect_to_signal,
                    self._APPLICATIONS_MANAGED_SIGNAL,
                    _applications_managed_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # and register it as a signal generated by us
                obj = self._registered_signals.setdefault(
                    self._APPLICATIONS_MANAGED_SIGNAL, [])
                obj.append(sig_match)

        const_debug_write(
            __name__,
            "_application_request_unlocked, about to 'schedule'")

        accepted = True
        if master:
            # disable the please wait signal
            self._please_wait(False)
            def _enqueue():
                return dbus.Interface(
                    self._entropy_bus,
                    dbus_interface=self.DBUS_INTERFACE
                    ).enqueue_application_action(
                        package_id, repository_id,
                        package_path, daemon_action,
                        simulate)

            def _enqueue_callback():
                return self._execute_mainloop(_enqueue)

            def _undo_callback():
                GLib.idle_add(
                    self.emit, "application-abort", app, daemon_action)

            box = QueueActionNotificationBox(
                app, daemon_action,
                _enqueue_callback, _undo_callback, None)
            self._nc.append_safe(box)
            const_debug_write(
                __name__,
                "service enqueue_application_action, about to sleep")
            accepted = box.acquire()
            if not accepted and sig_match is not None:
                # Undo request or not accepted, remove our signal handler
                # here
                sig_match.remove()
            # re-enable it
            self._please_wait(True)
            const_debug_write(
                __name__,
                "service enqueue_application_action, got: %s, type: %s" % (
                    accepted, type(accepted),))

        else:
            self._applications_managed_signal_check(
                sig_match, signal_sem,
                DaemonActivityStates.MANAGING_APPLICATIONS,
                LocalActivityStates.MANAGING_APPLICATIONS)

        return accepted

    def _applications_managed_signal_check(self, sig_match, signal_sem,
                                           daemon_activity,
                                           local_activity):
        """
        Called via _application_request_unlocked() in order to handle
        the possible race between RigoDaemon signal and the fact that
        we just lost it.
        This is only called in slave mode. When we didn't spawn the
        repositories update directly.
        """
        activity = self.activity()
        if activity == daemon_activity:
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
                      DaemonAppTransactionOutcome.SUCCESS,
                      "", local_activity)

    def _package_install_request(self, package_path, simulate=False):
        """
        Forward Application Package Install request to RigoDaemon.
        """
        with self._entropy.rwsem().writer():
            try:
                package_matches = self._entropy.add_package_repository(
                    package_path)
            except EntropyPackageException as exc:
                def _notify():
                    msg = _("Package Install Error: <i>%s</i>") % (exc,)
                    box = self.ServiceNotificationBox(
                        prepare_markup(msg),
                        Gtk.MessageType.ERROR,
                        context_id=self.PKG_INSTALL_CONTEXT_ID)
                    box.add_destroy_button(_("Okay"))
                    self._nc.append(box)
                GLib.idle_add(_notify)
                return

        accepted = False
        accepted_count = 0
        repository_ids = set()
        for package_match in package_matches:
            pkg_id, pkg_repo = package_match
            repository_ids.add(pkg_repo)
            app = Application(self._entropy, self._entropy_ws,
                              self, package_match,
                              package_path=package_path)
            accepted = self._application_request(
                app, AppActions.INSTALL, simulate=simulate)
            if not accepted:
                break
            accepted_count += 1

        if accepted_count == 0:
            with self._entropy.rwsem().writer():
                for repository_id in repository_ids:
                    self._entropy.remove_repository(
                        repository_id)
        else:
            for repository_id in repository_ids:
                self._package_repositories.append(
                    repository_id)

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
                    GLib.idle_add(
                        self.emit, "application-abort", app,
                        self._action_to_daemon_action(app_action))
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
                if master:
                    self._please_wait(True)
                accepted = self._application_request_unlocked(
                    app, daemon_action, master,
                    busied, simulate)
                if accepted is None:
                    # undo action requested by user
                    do_notify = False
                    accepted = False

            if not accepted:
                with self._application_request_mutex:
                    _unbusy()

                def _notify():
                    box = self.ServiceNotificationBox(
                        prepare_markup(
                            _("Another activity is currently in progress")
                        ),
                        Gtk.MessageType.ERROR,
                        context_id=self.ANOTHER_ACTIVITY_CONTEXT_ID)
                    box.add_destroy_button(_("K thanks"))
                    self._nc.append(box)
                if do_notify:
                    GLib.idle_add(_notify)

            # unhide please wait notification
            self._please_wait(False)

            return accepted

    def _upgrade_system_license_check(self):
        """
        Examine Applications that are going to be upgraded looking for
        licenses to read and accept.
        """
        with self._entropy.rwsem().reader():

            outcome = self._entropy.calculate_updates()

            update = outcome['update']
            if not update:
                return True

            licenses = self._entropy.get_licenses_to_accept(update)
            if not licenses:
                return True

        license_map = {}
        for lic_id, pkg_matches in licenses.items():
            obj = license_map.setdefault(lic_id, [])
            for pkg_match in pkg_matches:
                app = Application(
                    self._entropy, self._entropy_ws,
                    self, pkg_match)
                obj.append(app)

        const_debug_write(
            __name__,
            "_system_upgrade_license_checks: "
            "need to accept licenses: %s" % (license_map,))
        ask_meta = {
            'sem': Semaphore(0),
            'forever': False,
            'res': None,
        }
        GLib.idle_add(self._notify_blocking_licenses,
                      ask_meta, None, license_map)
        ask_meta['sem'].acquire()

        const_debug_write(
            __name__,
            "_system_upgrade_license_checks: "
            "unblock, accepted:: %s, forever: %s" % (
                ask_meta['res'], ask_meta['forever'],))

        if not ask_meta['res']:
            return False
        if ask_meta['forever']:
            self._accept_licenses(license_map.keys())
        return True

    def _upgrade_system_checks(self):
        """
        Examine System Upgrade Request before sending it to RigoDaemon.
        """
        # add license check
        accepted = self._upgrade_system_license_check()
        if not accepted:
            return False

        return True

    def _upgrade_system_unlocked(self, master, simulate):
        """
        Internal method handling the actual System Upgrade
        execution.
        """
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
                          "_upgrade_system_unlocked: "
                          "start-working")
        # don't check if UI is locked though

        signal_sem = Semaphore(1)

        def _applications_managed_signal(outcome, app_log_path):
            if not signal_sem.acquire(False):
                # already called, no need to call again
                return
            # this is done in order to have it called
            # only once by two different code paths
            self._applications_managed_signal(
                outcome, app_log_path,
                LocalActivityStates.UPGRADING_SYSTEM)

        with self._registered_signals_mutex:
            # connect our signal
            sig_match = self._execute_mainloop(
                self._entropy_bus.connect_to_signal,
                self._APPLICATIONS_MANAGED_SIGNAL,
                _applications_managed_signal,
                dbus_interface=self.DBUS_INTERFACE)

            # and register it as a signal generated by us
            obj = self._registered_signals.setdefault(
                self._APPLICATIONS_MANAGED_SIGNAL, [])
            obj.append(sig_match)

        const_debug_write(
            __name__,
            "_upgrade_system_unlocked, about to 'schedule'")

        accepted = True
        if master:
            def _upgrade():
                return dbus.Interface(
                    self._entropy_bus,
                    dbus_interface=self.DBUS_INTERFACE
                    ).upgrade_system(simulate)
            accepted = self._execute_mainloop(_upgrade)

            const_debug_write(
                __name__,
                "service upgrade_system, accepted: %s" % (
                    accepted,))

            def _notify():
                msg = prepare_markup(
                    _("<b>System Upgrade</b> has begun, "
                      "now go make some coffee"))
                box = self.ServiceNotificationBox(
                    msg, Gtk.MessageType.INFO,
                    context_id=self.SYSTEM_UPGRADE_CONTEXT_ID
                    )
                self._nc.append(box, timeout=10)
            if accepted:
                GLib.idle_add(_notify)

        else:
            self._applications_managed_signal_check(
                sig_match, signal_sem,
                DaemonActivityStates.UPGRADING_SYSTEM,
                LocalActivityStates.UPGRADING_SYSTEM)

        return accepted

    def _upgrade_system(self, simulate, master=True):
        """
        Forward a System Upgrade Request to RigoDaemon.
        """
        # This code has a lot of similarities wtih the application
        # request one.
        with self._application_request_mutex:
            # since we need to writer_acquire(), which is blocking
            # better try to allocate the local activity first
            local_activity = LocalActivityStates.UPGRADING_SYSTEM
            try:
                self.busy(local_activity)
            except LocalActivityStates.BusyError:
                const_debug_write(__name__, "_upgrade_system: "
                                  "LocalActivityStates.BusyError!")
                # doing other stuff, cannot go ahead
                return False
            except LocalActivityStates.SameError:
                const_debug_write(__name__, "_upgrade_system: "
                                  "LocalActivityStates.SameError, "
                                  "aborting")
                return False

            # 3 -- ACTIVITY CRIT :: ON
            const_debug_write(__name__, "_upgrade_system: "
                              "about to acquire writer end of "
                              "activity rwsem")
            self._activity_rwsem.writer_acquire() # CANBLOCK

            def _unbusy():
                self.unbusy(local_activity)
                # 3 -- ACTIVITY CRIT :: OFF
                self._activity_rwsem.writer_release()

            # clean terminal, make sure no crap is left there
            if self._terminal is not None:
                self._terminal.reset()

        do_notify = True
        accepted = True
        if master:
            accepted = self._upgrade_system_checks()
            if not accepted:
                do_notify = False
            const_debug_write(
                __name__,
                "_upgrade_system, checks result: %s" % (
                    accepted,))

        if accepted:
            if master:
                self._please_wait(True)
            accepted = self._upgrade_system_unlocked(
                master, simulate)

        if not accepted:
            with self._application_request_mutex:
                _unbusy()

            def _notify():
                box = self.ServiceNotificationBox(
                    prepare_markup(
                        _("Another activity is currently in progress")
                    ),
                    Gtk.MessageType.ERROR,
                    context_id=self.ANOTHER_ACTIVITY_CONTEXT_ID)
                box.add_destroy_button(_("K thanks"))
                self._nc.append(box)
            if do_notify:
                GLib.idle_add(_notify)

        # unhide please wait notification
        self._please_wait(False)

        return accepted
