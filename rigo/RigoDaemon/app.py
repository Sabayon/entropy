#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-3

    B{Entropy Package Manager Rigo Daemon}.

"""
import os
import stat
import random
random.seed()

# entropy.i18n will pick this up
os.environ['ETP_GETTEXT_DOMAIN'] = "rigo"

# Set the default terminal if unset
os.environ["TERM"] = os.environ.get("TERM", "xterm")

import contextlib
import errno
import sys
import time
import signal
import shutil
import subprocess
import copy
import threading
from collections import deque

# this makes the daemon to not write the entropy pid file
# avoiding to lock other instances
sys.argv.append('--no-pid-handling')

import dbus
import dbus.service
import dbus.mainloop.glib

from gi.repository import GLib, GObject, Gio

DAEMON_LOGGING = False
DAEMON_DEBUG = False
if "--debug" in sys.argv:
    sys.argv.remove("--debug")
    DAEMON_DEBUG = True
if "--daemon-logging" in sys.argv:
    sys.argv.remove("--daemon-logging")
    DAEMON_LOGGING = True

# Entropy imports
sys.path.insert(0, '/usr/lib/rigo')
sys.path.insert(0, '/usr/lib/entropy/lib')
sys.path.insert(0, '../../lib')
sys.path.insert(0, '../lib')
sys.path.insert(0, './')

from entropy.cache import EntropyCacher
# update default writeback timeout
EntropyCacher.WRITEBACK_TIMEOUT = 120

# Change the default in-RAM cache policy for repositories in order to
# save a huge amount of RAM.
from entropy.db.cache import EntropyRepositoryCachePolicies
_NONE_POL = EntropyRepositoryCachePolicies.NONE
EntropyRepositoryCachePolicies.DEFAULT_CACHE_POLICY = _NONE_POL

from entropy.const import etpConst, const_convert_to_rawstring, \
    initconfig_entropy_constants, const_debug_write, dump_signal, \
    const_mkstemp
from entropy.locks import EntropyResourcesLock, UpdatesNotificationResourceLock
from entropy.exceptions import DependenciesNotFound, \
    DependenciesCollision, DependenciesNotRemovable, SystemDatabaseError, \
    EntropyPackageException, InterruptError, RepositoryError
from entropy.i18n import _
from entropy.misc import LogFile, ParallelTask, TimeScheduled, \
    ReadersWritersSemaphore
from entropy.fetchers import UrlFetcher, MultipleUrlFetcher
from entropy.output import TextInterface, purple, teal
from entropy.client.interfaces import Client
from entropy.client.interfaces.package.actions.action import PackageAction
from entropy.client.interfaces.noticeboard import NoticeBoard
from entropy.client.interfaces.repository import Repository
from entropy.client.interfaces.package.preservedlibs import PreservedLibraries
from entropy.services.client import WebService
from entropy.core.settings.base import SystemSettings

import kswitch

import entropy.tools
import entropy.dep

from RigoDaemon.enums import ActivityStates, AppActions, \
    AppTransactionOutcome, AppTransactionStates
from RigoDaemon.config import DbusConfig, PolicyActions
from RigoDaemon.authentication import AuthenticationController

TEXT = TextInterface()
DAEMON_LOGFILE = os.path.join(etpConst['syslogdir'], "rigo-daemon.log")
DAEMON_LOG = LogFile(SystemSettings()['system']['log_level']+1,
    DAEMON_LOGFILE, header = "[rigo-daemon]")

if DAEMON_LOGGING:
    # redirect possible exception tracebacks to log file
    sys.stderr = DAEMON_LOG
    sys.stdout = DAEMON_LOG

_MAIN_THREAD = threading.current_thread()


def get_entropy_webservice(entropy_client, repository_id, tx_cb = False):
    """
    Get Entropy Web Services service object (ClientWebService).

    @param entropy_client: Entropy Client interface
    @type entropy_client: entropy.client.interfaces.Client
    @param repository_id: repository identifier
    @type repository_id: string
    @return: the ClientWebService instance
    @rtype: entropy.client.services.interfaces.ClientWebService
    @raise WebService.UnsupportedService: if service is unsupported by
        repository
    """
    def _transfer_callback(transfered, total, download):
        if download:
            action = _("Downloading")
        else:
            action = _("Uploading")

        percent = 100
        if (total > 0) and (transfered <= total):
            percent = int(round((float(transfered)/total) * 100, 1))

        msg = "[%s%s] %s ..." % (purple(str(percent)), "%", teal(action))
        entropy_client.output(msg, back=True)

    factory = entropy_client.WebServices()
    webserv = factory.new(repository_id)
    if tx_cb:
        webserv._set_transfer_callback(_transfer_callback)
    return webserv

def write_output(message, debug=False):
    message = time.strftime('[%H:%M:%S %d/%m/%Y %Z]') + " " + message
    if DAEMON_LOGGING:
        if (debug and DAEMON_DEBUG) or (not debug):
            DAEMON_LOG.write(message)
            DAEMON_LOG.flush()
    if DAEMON_DEBUG:
        if debug:
            const_debug_write(
                __name__, message, force=True,
                stdout=sys.__stdout__)
        else:
            TEXT.output(message)

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def handle_exception(_exc_class, exc_instance, exc_tb):
    t_back = entropy.tools.get_traceback(tb_obj = exc_tb)
    # restore original exception handler, to avoid loops
    uninstall_exception_handler()
    # write exception to log file
    write_output(const_convert_to_rawstring(t_back), debug=True)
    raise exc_instance

install_exception_handler()

class Entropy(Client):

    _DAEMON = None
    _ACTION_QUEUE_THREAD = None

    def init_singleton(self):
        Client.init_singleton(
            self, load_ugc=False,
            url_fetcher=DaemonUrlFetcher,
            multiple_url_fetcher=DaemonMultipleUrlFetcher,
            repo_validation=False)
        write_output(
            "Loading Entropy Rigo daemon: logfile: %s" % (
                DAEMON_LOGFILE,)
            )

    @staticmethod
    def set_daemon(daem, worker):
        """
        Bind the Entropy Singleton instance to the DBUS Daemon.
        """
        Entropy._DAEMON = daem
        Entropy._ACTION_QUEUE_THREAD = worker
        DaemonUrlFetcher.set_daemon(daem)
        DaemonMultipleUrlFetcher.set_daemon(daem)

    @classmethod
    def output(cls, text, header = "", footer = "", back = False,
               importance = 0, level = "info", count = None,
               percent = False, _raw=False):
        if cls._DAEMON is not None:
            count_c = 0
            count_t = 0
            if count is not None:
                count_c, count_t = count
            GLib.idle_add(
                cls._DAEMON.output,
                text, header, footer, back, importance,
                level, count_c, count_t, percent, _raw)

    @classmethod
    def isMainThread(cls, thread_obj):
        if thread_obj is Entropy._ACTION_QUEUE_THREAD:
            return True
        if thread_obj is _MAIN_THREAD:
            return True
        return False

    @classmethod
    def get_repository(cls, repository_id):
        """
        Monkey patch repository class objects with an appropriate
        version of isMainThread.

        This avoids EntropySQLRepository instances to start multiple
        cleanup monitors for the ActionQueueWorkerThread, which can
        be considered a second "MainThread" for repository instances.
        """
        repo_class = super(Entropy, cls).get_repository(repository_id)
        repo_class.isMainThread = Entropy.isMainThread
        return repo_class


Client.__singleton_class__ = Entropy
TextInterface.output = Entropy.output

class DaemonUrlFetcher(UrlFetcher):

    _DAEMON = None

    def __init__(self, *args, **kwargs):
        UrlFetcher.__init__(self, *args, **kwargs)
        self.__average = 0
        self.__downloadedsize = 0
        self.__remotesize = 0
        self.__datatransfer = 0
        self.__time_remaining = ""
        self.__last_t = None

    @staticmethod
    def set_daemon(daem):
        """
        Bind RigoDaemon instance to this class.
        """
        DaemonUrlFetcher._DAEMON = daem

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        self.__average = average
        self.__downloadedsize = downloaded_size
        self.__remotesize = total_size
        self.__datatransfer = data_transfer
        self.__time_remaining = time_remaining

    def update(self):
        if self._DAEMON is None:
            return

        # avoid flooding clients
        last_t = self.__last_t
        cur_t = time.time()
        if last_t is not None:
            if (cur_t - last_t) < 0.5:
                return # dont flood
        self.__last_t = cur_t

        GLib.idle_add(
            self._DAEMON.transfer_output,
            self.__average, self.__downloadedsize,
            int(self.__remotesize), int(self.__datatransfer),
            self.__time_remaining)


class DaemonMultipleUrlFetcher(MultipleUrlFetcher):

    _DAEMON = None

    def __init__(self, *args, **kwargs):
        MultipleUrlFetcher.__init__(self, *args, **kwargs)
        self.__last_t = None
        self.__last_t_mutex = threading.Lock()

    @staticmethod
    def set_daemon(daem):
        """
        Bind RigoDaemon instance to this class.
        """
        DaemonMultipleUrlFetcher._DAEMON = daem

    def update(self):
        if self._DAEMON is None:
            return

        # avoid flooding clients
        with self.__last_t_mutex:
            last_t = self.__last_t
            cur_t = time.time()
            if last_t is not None:
                if (cur_t - last_t) < 0.5:
                    return # dont flood
            self.__last_t = cur_t

        stats = self._compute_progress_stats()

        if stats["all_started"]:
            GLib.idle_add(
                self._DAEMON.transfer_output,
                stats["average"], stats["downloaded_size"],
                stats["total_size"], stats["data_transfer"],
                stats["time_remaining_str"])


class FakeOutFile(object):

    """
    Fake Standard Output / Error file object
    """

    def __init__(self, entropy_client, app_mgmt_mutex, app_mgmt_notes):
        self._entropy = entropy_client
        self._app_mgmt_mutex = app_mgmt_mutex
        self._app_mgmt_notes = app_mgmt_notes
        self._rfd, self._wfd = os.pipe()
        task = ParallelTask(self._pusher)
        task.name = "FakeOutFilePusher"
        task.daemon = True
        task.start()

    def _pusher(self):
        while True:
            try:
                chunk = os.read(self._rfd, 512) # BLOCKS
            except (IOError, OSError) as err:
                # both can raise EINTR
                if err.errno == errno.EINTR:
                    continue
                raise
            # record to App Management Log, if enabled
            with self._app_mgmt_mutex:
                fobj = self._app_mgmt_notes['fobj']
                if fobj is not None:
                    try:
                        fobj.write(chunk)
                    except (OSError, IOError) as err:
                        write_output("_pusher thread: "
                                     "cannot write to app log: "
                                     "%s" % (repr(err),))
            self._entropy.output(chunk, _raw=True)

    def close(self):
        pass

    def flush(self):
        pass

    def fileno(self):
        return self._wfd

    def isatty(self):
        return False

    def read(self, _a):
        return ""

    def readline(self):
        return ""

    def readlines(self):
        return []

    def write(self, s):
        self._entropy.output(s, _raw=True)

    def write_line(self, s):
        self.write(s)

    def writelines(self, l):
        for s in l:
            self.write(s)

    def seek(self, _a):
        raise IOError(29, "Illegal seek")

    def tell(self):
        raise IOError(29, "Illegal seek")

    def truncate(self):
        self.tell()


class ApplicationsTransaction(object):

    """
    RigoDaemon Application Transaction Controller.
    """

    def __init__(self):
        self._transactions = {}
        self._transactions_mutex = threading.RLock()
        self._parent = None

    def __enter__(self):
        """
        Hold the mutex using the with statement.
        """
        self._transactions_mutex.acquire()

    def __exit__(self, exc_type, exc_value, tb):
        """
        Release the mutex exiting from the with statement.
        """
        self._transactions_mutex.release()

    def set_parent(self, item):
        """
        Set the parent Application. All the other Applications
        listed here are belonging from this one.
        """
        self._parent = item

    def unset_parent(self):
        """
        Unset the parent Application.
        """
        self._parent = None

    def set(self, package_id, repository_id, app_action):
        """
        Set transaction state for Application.
        """
        with self._transactions_mutex:
            match = (package_id, repository_id)
            self._transactions[match] = app_action

    def unset(self, package_id, repository_id):
        """
        Unset transaction state for Application.
        """
        with self._transactions_mutex:
            match = (package_id, repository_id)
            self._transactions.pop(match, None)

    def reset(self):
        """
        Reset all the transaction states.
        """
        with self._transactions_mutex:
            self._transactions.clear()
            self.unset_parent()

    def get_parent(self):
        """
        Return the parent Application metadata, if any.
        Otherwise return None.
        """
        return self._parent

    def get(self, package_id, repository_id):
        """
        Get transaction state (in for of AppActions enum)
        for given Application.
        """
        with self._transactions_mutex:
            match = (package_id, repository_id)
            tx = self._transactions.get(match)
            if tx is None:
                return AppActions.IDLE
        return tx

    def all(self):
        """
        Return the list of Applications currently listed
        in ApplicationsTransactions.
        Each list item is composed by the following tuple:
        (package_id, repository_id, action)
        """
        items = []
        with self._transactions_mutex:
            for (pkg_id, repository_id), action in self._transactions.items():
                items.append((pkg_id, repository_id, action))
        return items


class RigoDaemonService(dbus.service.Object):

    """
    RigoDaemon is the dbus service Object in charge of executing
    privileged tasks, like repository updates, package installation
    and removal and so on.
    Mutual exclusion with other Entropy instances must be handled
    by the caller. Here it is assumed that Entropy Resources Lock
    is acquired in exclusive mode.
    """

    BUS_NAME = DbusConfig.BUS_NAME
    OBJECT_PATH = DbusConfig.OBJECT_PATH

    _INSTALLED_REPO_GIO_EVENTS = (
        Gio.FileMonitorEvent.ATTRIBUTE_CHANGED,
        Gio.FileMonitorEvent.CHANGED)

    API_VERSION = 8

    class ActionQueueItem(object):

        def __init__(self, package_id, repository_id, package_path,
                     action, simulate, authorized):
            self._package_id = package_id
            self._repository_id = repository_id
            self._path = package_path
            self._action = action
            self._simulate = simulate
            self._authorized = authorized
            self._parent = False

        @property
        def pkg(self):
            """
            Get package match for Application.
            """
            return (self._package_id, self._repository_id)

        def repository_id(self):
            """
            Return Repository Identifier of package.
            """
            return self._repository_id

        def path(self):
            """
            Return Application Package file path, if any.
            """
            return self._path

        def action(self):
            """
            Return AppActions Action for this ActionQueueItem.
            """
            return self._action

        def simulate(self):
            """
            Return True, if Action should be simulated only.
            """
            return self._simulate

        def authorized(self):
            """
            Return True, if Action has been authorized.
            """
            return self._authorized

        def set_authorized(self, val):
            """
            Set a new authorization value.
            """
            self._authorized = val

        def parent(self):
            """
            Return True, if this Application is the one being
            currently processed.
            """
            return self._parent

        def set_parent(self, parent):
            """
            Set the current parent metadata State.
            If parent is True, the Application is being
            currently processed.
            """
            self._parent = parent

        def __str__(self):
            """
            Show item in human readable way
            """
            return "ActionQueueItem{%s, %s, %s}" % (
                self.pkg, self.action(), self.simulate())

        def __repr__(self):
            """
            Same as __str__
            """
            return str(self)

    class UpgradeActionQueueItem(object):

        def __init__(self, simulate, authorized):
            self._simulate = simulate
            self._authorized = authorized
            self._parent = False

        def simulate(self):
            """
            Return True, if Action should be simulated only.
            """
            return self._simulate

        def action(self):
            """
            Return AppActions Action for this UpgradeActionQueueItem.
            """
            return AppActions.UPGRADE

        def authorized(self):
            """
            Return True, if Action has been authorized.
            """
            return self._authorized

        def set_authorized(self, val):
            """
            Set a new authorization value.
            """
            self._authorized = val

        def parent(self):
            """
            Return True, if this Action is the one being
            currently processed.
            """
            return self._parent

        def set_parent(self, parent):
            """
            Set the current parent metadata State.
            If parent is True, the Action is being
            currently processed.
            """
            self._parent = parent

        def __str__(self):
            """
            Show item in human readable way
            """
            return "UpgradeActionQueueItem{simulate=%s}" % (
                self.simulate())

        def __repr__(self):
            """
            Same as __str__
            """
            return str(self)


    def __init__(self):
        self._thread_dumper()
        object_path = RigoDaemonService.OBJECT_PATH
        dbus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default = True)
        system_bus = dbus.SystemBus(mainloop = dbus_loop)
        self._bus = system_bus
        name = dbus.service.BusName(RigoDaemonService.BUS_NAME,
                                    bus = system_bus)
        dbus.service.Object.__init__(self, name, object_path)

        # protects against concurrent entropy shared objects
        # (like EntropyRepository) while in use.
        self._rwsem = ReadersWritersSemaphore()

        # Polkit-based authentication controller
        self._auth = AuthenticationController()

        self._txs = ApplicationsTransaction()
        # used by non-daemon thread to exit
        self._stop_signal = False
        # used by clients to interrupt an ongoing activity
        self._interrupt_activity = False

        # original standard output and error files
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr

        # used to determine if there are connected clients
        self._ping_timer_mutex = threading.Lock()
        self._ping_timer = None

        self._current_activity_mutex = threading.Lock()
        self._current_activity = ActivityStates.AVAILABLE
        self._activity_mutex = threading.Lock()

        self._acquired_exclusive = False
        self._acquired_exclusive_mutex = threading.Lock()

        self._config_updates = None
        self._config_updates_mutex = threading.Lock()

        self._greetings_serializer = threading.Lock()
        # Thread serializer for Entropy SystemSettings
        # active management.
        self._settings_mgmt_serializer = threading.Lock()

        # this mutex is used when non threads-safe
        # accesses are required, like when we're forced
        # to iterate through the deque.
        self._action_queue_mutex = threading.Lock()
        self._action_queue = deque()
        # this should not be merged with action_queue_mutex
        # because it masks clients from early action_queue_length = 0
        # return values (see action_queue_length()).
        self._action_queue_length_mutex = threading.Lock()
        self._action_queue_length = 0
        self._action_queue_waiter = threading.Semaphore(0)
        self._enqueue_action_busy_hold_sem = threading.Semaphore()
        self._action_queue_task = ParallelTask(
            self._action_queue_worker_thread)
        self._action_queue_task.name = "ActionQueueWorkerThread"
        self._action_queue_task.daemon = True
        self._action_queue_task.start()

        self._deferred_shutdown = False
        self._deferred_shutdown_mutex = threading.Lock()

        self._app_mgmt_mutex = threading.Lock()
        self._app_mgmt_notes = {
            'fobj': None,
            'path': None
        }

        Entropy.set_daemon(self, self._action_queue_task)
        self._entropy = Entropy()
        # keep all the resources closed
        self._close_local_resources()

        self._reslock = EntropyResourcesLock(output=self._entropy)

        self._fakeout = FakeOutFile(
            self._entropy,
            self._app_mgmt_mutex,
            self._app_mgmt_notes)

        executable_path = sys.argv[0]
        write_output(
            "__init__: dbus service loaded, "
            "pid: %d, ppid: %d, exec: %s" %  (
                os.getpid(), os.getppid(),
                executable_path,)
            )

        # monitor daemon executable changes and installed
        # repository changes
        # the latter is mainly for lockless clients
        repo_path = self._entropy.installed_repository_path()
        bounded_sem = threading.BoundedSemaphore(1)
        self._installed_repository_updated_serializer = bounded_sem
        self._inst_mon = None
        if os.path.isfile(repo_path):
            inst_repo_file = Gio.file_new_for_path(repo_path)
            self._inst_mon = inst_repo_file.monitor_file(
                Gio.FileMonitorFlags.NONE, None)
            self._inst_mon.connect(
                "changed", self._installed_repository_changed)

        self._exec_mon = None
        if os.path.isfile(executable_path):
            exec_file = Gio.file_new_for_path(executable_path)
            self._exec_mon = exec_file.monitor_file(
                Gio.FileMonitorFlags.NONE, None)
            self._exec_mon.connect(
                "changed", self._rigo_daemon_executable_changed)

        self._start_package_cache_timer()
        self._start_repositories_update_timer()
        self._start_timed_reload()

    def _thread_dumper(self):
        """
        If --dumper is in argv, a recurring thread dump
        function will be spawned every 30 seconds.
        """
        dumper_enable = DAEMON_DEBUG
        if dumper_enable:
            task = None

            def _dumper():
                def _dump():
                    task.kill()
                    dump_signal(None, None)
                timer = threading.Timer(10.0, _dump)
                timer.name = "MainThreadHearthbeatCheck"
                timer.daemon = True
                timer.start()
                GLib.idle_add(timer.cancel)

            task = TimeScheduled(5.0, _dumper)
            task.name = "ThreadDumper"
            task.daemon = True
            task.start()

    def _start_timed_reload(self):
        """
        Start timer thread that reloads RigoDaemon every 24 hours.
        This avoids the Python process to grow over time.
        """
        task = threading.Timer(3600 * 24, self.reload)
        task.daemon = True
        task.name = "TimedReloadTimer"
        task.start()

    def _start_package_cache_timer(self):
        """
        Start timer thread that handles old package files
        removal.
        """
        # clean entropy packages cache every 8 hours, basing
        # on Entropy Client settings
        task = threading.Timer(3600 * 8, self._clean_package_cache)
        task.daemon = True
        task.name = "CleanPackageCacheTimer"
        task.start()

    def _start_repositories_update_timer(self):
        """
        Start timer thread that handles automatic repositories
        update.
        """
        task = threading.Timer(
            random.randint(3600 * 1, 3600 * 18),
            self._auto_repositories_update)
        task.daemon = True
        task.name = "AutoRepositoriesUpdateTimer"
        task.start()

    def _installed_repository_changed(self, _mon, _gio_f, _data, event):
        """
        Gio handler for Installed Packages Repository
        modification events.
        """
        if event not in self._INSTALLED_REPO_GIO_EVENTS:
            return

        serializer = self._installed_repository_updated_serializer
        acquired = False
        started = False
        try:

            # cannot block in this thread (it's the MainThread)
            acquired = serializer.acquire(False)
            if not acquired:
                write_output("_installed_repository_changed: "
                             "serializer already acquired, "
                             "we're already sleeping, skipping",
                             debug=True)
                return

            # pass the lock (semaphore) to our child thread
            # so that no other threads will be able to get
            # here before the worker is done completely.
            # this way we are 100% sure that no other damn
            # threads get to here and avoid bursts completely.
            write_output("_installed_repository_changed: "
                         "launching thread", debug=True)
            task = ParallelTask(
                self._installed_repository_updated,
                serializer)
            task.name = "InstalledRepositoryCheckHandler"
            task.daemon = True
            task.start()
            started = True

        finally:
            if not started and acquired:
                # this means that the serializer has been acquired
                # but the thread wasn't able to start, which is
                # the French for exceptions OMG. Thus, release the
                # semaphore explicitly
                write_output("_installed_repository_updated: "
                             "serializer acquired, thread dead, "
                             "releasing the semaphore !!",
                             debug=True)
                serializer.release()

    def _rigo_daemon_executable_changed(self, _mon, _gio_f, _data, _event):
        """
        Gio handler for RigoDaemon executable modification events.
        """
        write_output("RigoDaemon executable changed, "
                     "%s" % (locals(),), debug=True)
        if not self._deferred_shutdown:
            task = ParallelTask(
                self._activate_deferred_shutdown)
            task.name = "ActivateDeferredShutdown"
            task.start()

    def _activate_deferred_shutdown(self, *_args):
        """
        Activate deferred shutdown starting the ping/pong
        protocol.
        """
        with self._deferred_shutdown_mutex:
            if self._deferred_shutdown:
                return
            self._deferred_shutdown = True

        GLib.idle_add(self.deferred_shutdown)
        write_output("Activating deferred shutdown...", debug=True)
        def _ping():
            GLib.idle_add(self.ping)
        task = TimeScheduled(30.0, _ping)
        task.set_delay_before(False)
        task.name = "ShutdownPinger"
        task.daemon = True
        task.start()

    def _systemd_booted(self):
        """
        Return whether systemd booted this system.
        """
        return os.path.isdir("/run/systemd/system")

    def _systemd_inhibit_shutdown(self, activity):
        """
        Inhibit shutdown through systemd. Return the file descriptor
        that should be kept open as long as the shutdown should be
        inhibited.
        """
        write_output("_systemd_inhibit_shutdown: called", debug=True)

        description = _("Internal activity in progress")
        if activity == ActivityStates.UPGRADING_SYSTEM:
            description = _("Upgrade in progress")
        elif activity == ActivityStates.UPDATING_REPOSITORIES:
            description = _("Repositories update in progress")
        elif activity == ActivityStates.MANAGING_APPLICATIONS:
            description = _("Applications management in progress")

        def getfd():
            try:
                bus = self._bus.get_object(
                    "org.freedesktop.login1",
                    "/org/freedesktop/login1")
                iface = dbus.Interface(
                    bus, dbus_interface="org.freedesktop.login1.Manager")

                return iface.Inhibit(
                    "shutdown:idle", "RigoDaemon",
                    description, "block").take()

            except dbus.exceptions.DBusException as err:
                write_output("_systemd_inhibit: error: %s" % (err,))

        return self._execute_mainloop(getfd)

    @contextlib.contextmanager
    def _inhibit_shutdown(self, activity):
        """
        Context manager that can be used to inhibit the system shutdown.
        """
        write_output("_inhibit_shutdown: called", debug=True)
        fd = None
        try:
            if self._systemd_booted():
                fd = self._systemd_inhibit_shutdown(activity)

            write_output("_inhibit_shutdown: got fd: %s" % (fd,),
                         debug=True)

            yield

        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _clean_package_cache(self):
        """
        Clean Entropy Packages Cache, removing old package
        files.
        """
        with self._activity_mutex:
            self._acquire_shared()
            try:

                with self._rwsem.reader():
                    try:
                        self._entropy.clean_downloaded_packages(
                            skip_available_packages=True)
                    except AttributeError:
                        pass

            finally:
                self._release_shared()
                # spin!
                self._start_package_cache_timer()

    def _auto_repositories_update(self):
        """
        Execute automatic Repositories Update Activity.
        """
        # Add entropy to the scheduled execution to
        # avoid bursts against the web service
        rand_secs = random.randint(1800, 7200)
        time.sleep(rand_secs)

        if self._is_system_on_batteries():
            self._start_repositories_update_timer()
            return

        activity = ActivityStates.UPDATING_REPOSITORIES
        acquired = False
        busied = False
        spin = False
        with self._activity_mutex:
            try:
                acquired = self._acquire_exclusive_simple_nb()
                if not acquired:
                    write_output("_auto_update_repositories: "
                                 "lock not acquired",
                                 debug=True)
                    spin = True
                    return

                try:
                    self._busy(activity)
                    busied = True
                except ActivityStates.BusyError:
                    write_output("_auto_update_repositories: I'm busy",
                                 debug=True)
                    spin = True
                    return
                except ActivityStates.SameError:
                    write_output("_auto_update_repositories: "
                                 "already doing it",
                                 debug=True)
                    spin = True
                    return

                write_output("_auto_update_repositories: "
                             "busied: %s" % (busied,),
                             debug=True)

            finally:
                if acquired:
                    self._release_exclusive_simple_nb()
                if spin:
                    self._start_repositories_update_timer()

        if busied:
            try:
                write_output("_auto_update_repositories: "
                             "spawning _update_repositories",
                             debug=True)
                self._update_repositories(
                    [], False, activity, None,
                    authorized=True)
                write_output("_auto_update_repositories: "
                             "_update_repositories terminated",
                             debug=True)
            finally:
                self._start_repositories_update_timer()

    def _is_system_on_batteries(self):
        """
        Return whether System is running on batteries.
        """
        ac_powa_exec = "/usr/bin/on_ac_power"
        if not os.path.lexists(ac_powa_exec):
            return False
        ex_rc = os.system(ac_powa_exec)
        if ex_rc:
            return True
        return False

    def _enable_stdout_stderr_redirect(self):
        """
        Enable standard output and standard error redirect to
        Entropy.output()
        """
        if DAEMON_DEBUG:
            return
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stderr = self._fakeout
        sys.stdout = self._fakeout

    def _disable_stdout_stderr_redirect(self):
        """
        Disable standard output and standard error redirect to file.
        """
        if DAEMON_DEBUG:
            return
        sys.stderr = self._old_stderr
        sys.stdout = self._old_stdout

    def _busy(self, activity):
        """
        Switch to busy activity state, if possible.
        Raise ActivityStates.BusyError if already busy.
        """
        with self._current_activity_mutex:
            if self._current_activity == activity:
                raise ActivityStates.SameError()
            if self._current_activity != ActivityStates.AVAILABLE:
                raise ActivityStates.BusyError()
            self._current_activity = activity

    def _unbusy(self, activity, _force=False):
        """
        Unbusy from previous Activity.
        Raise ActivityStates.AlreadyAvailableError if already
        AVAILABLE.
        Raise ActivityStates.UnbusyFromDifferentActivity if
        provided activity differs from the current one.
        """
        with self._current_activity_mutex:
            if activity != self._current_activity and not _force:
                raise ActivityStates.UnbusyFromDifferentActivity(
                    "unbusy from: %s, current: %s" % (
                        activity, self._current_activity,))
            if activity == ActivityStates.AVAILABLE and not _force:
                raise ActivityStates.AlreadyAvailableError()
            self._current_activity = ActivityStates.AVAILABLE

    def _get_caller_pid(self, sender):
        """
        Return the PID of the caller (through Dbus).
        """
        bus = self._bus.get_object(
            'org.freedesktop.DBus',
            '/org/freedesktop/DBus')
        return dbus.Interface(
            bus,
            'org.freedesktop.DBus').GetConnectionUnixProcessID(
            sender)

    def _get_caller_user(self, sender):
        """
        Return the username of the caller (through Dbus).
        """
        bus = self._bus.get_object(
            'org.freedesktop.DBus',
            '/org/freedesktop/DBus')
        return dbus.Interface(
            bus,
            'org.freedesktop.DBus').GetConnectionUnixUser(
            sender)

    def _dbus_to_unicode(self, dbus_string):
        """
        Convert dbus.String() to unicode object
        """
        return dbus_string.decode(etpConst['conf_encoding'])

    def _execute_mainloop(self, function, *args, **kwargs):
        """
        Execute a function inside the MainLoop and return
        the result to the caller.
        """
        if threading.current_thread().name == "MainThread":
            return function(*args, **kwargs)

        sem_data = {
            'sem': threading.Semaphore(0),
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

    def _authorize(self, pid, action_id):
        """
        Authorize privileged Activity.
        Return True for success, False for failure.
        """
        write_output("_authorize: enter", debug=True)
        auth_res = {
            'sem': threading.Semaphore(0),
            'result': None,
            }

        def _authorized_callback(result):
            write_output("_authorize: received callback: %s" % (
                    result,), debug=True)
            auth_res['result'] = result
            auth_res['sem'].release()

        write_output("_authorize: got pid: %s" % (pid,), debug=True)
        GLib.idle_add(
            self._auth.authenticate,
            pid, action_id, _authorized_callback)
        write_output("_authorize: sleeping on sem",
            debug=True)

        auth_res['sem'].acquire()
        write_output("_authorize: got result: %s" % (
                auth_res['result'],),
            debug=True)

        return auth_res['result']

    def _authorize_sync(self, pid, action_id):
        """
        Authorize privileged Activity (synchronous method).
        Return True for success, False for failure.
        """
        return self._auth.authenticate_sync(
            pid, action_id)

    def stop(self):
        """
        RigoDaemon exit method.
        """
        write_output("stop(): called", debug=True)
        with self._activity_mutex:
            self._stop_signal = True
            self._action_queue_waiter.release()
            self._close_local_resources()
            write_output("stop(): activity mutex acquired, quitting",
                         debug=True)

            entropy.tools.kill_threads()

            sem = threading.Semaphore(0)
            def _shutdown(_sem):
                self.shutdown()
                _sem.release()
            GLib.idle_add(_shutdown, sem)
            sem.acquire()
            # give receivers some time
            time.sleep(2.0)

            # use kill so that GObject main loop will quit as well
            os.kill(os.getpid(), signal.SIGTERM)

    def _installed_repository_updated(self, serializer):
        """
        Callback spawned when Installed Repository directory content
        changes.
        Attention: this method is called with serializer acquired.
        """

        # check whether we are allowed to send notifications
        # to the user. Also, this is a best effort to stop
        # nagging the user when Equo or other tools are
        # installing packages.
        # Internally, we use the activity mutex so there is no
        # need to deal with this lock in our own action queue.
        # We should sleep here rather than using non blocking
        # locking because we want to eventually notify the user
        # of the available updates.
        notification_lock = UpdatesNotificationResourceLock(
            output=self._entropy)

        notif_acquired = False
        schedule_new = False
        try:
            with self._activity_mutex:

                notif_acquired = notification_lock.try_acquire_exclusive()
                if not notif_acquired:
                    # then give up and schedule a new signal callback as soon
                    # as the notification lock is acquired
                    schedule_new = True

                else:
                    self._acquire_shared()
                    try:
                        self._close_local_resources()
                        self._entropy_setup()

                        with self._rwsem.reader():
                            self._installed_repository_updated_unlocked()
                    finally:
                        self._release_shared()

        finally:
            write_output("_installed_repository_updated: "
                         "releasing serializer (baton)",
                         debug=True)
            if notif_acquired:
                notification_lock.release()

            if not schedule_new:
                # release the serializer object that our parent gave us.
                # Note that if schedule_new is True, we're going to be
                # called again. For this reason, we do not release the
                # serializer lock in this case.
                serializer.release()

        if schedule_new:
            write_output("_installed_repository_updated: "
                         "notification lock held, scheduling a new "
                         "check as soon as the lock is acquired.",
                         debug=True)

            def lock_sleep():
                nlock = UpdatesNotificationResourceLock(
                    output=self._entropy)
                with nlock.exclusive():  # blocks
                    task = ParallelTask(
                        self._installed_repository_updated,
                        serializer)
                    task.name = "RescheduledInstalledRepositoryCheckHandler"
                    task.daemon = True
                    task.start()

            stask = ParallelTask(lock_sleep)
            stask.name = "SleepingOnUpdatesNotificationResourceLock"
            stask.daemon = True
            stask.start()

    def _installed_repository_updated_unlocked(self):
        """
        Unlocked (not activity mutex, no shared locking, no
        rwsem) version of _installed_repository_updated()
        """
        write_output("_installed_repository_updated_unlocked:"
                     " called, sending signal",
                     debug=True)

        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():
            outcome = self._entropy.calculate_updates()

            remove_atoms = []
            for pkg_id in outcome['remove']:
                atom = inst_repo.retrieveAtom(pkg_id)
                if atom is not None:
                    remove_atoms.append(atom)

        update_atoms = []
        for pkg_id, repo_id in outcome['update']:
            atom = self._entropy.open_repository(
                repo_id).retrieveAtom(pkg_id)
            if atom is not None:
                update_atoms.append(atom)

        # KernelSwitcher is already process/thread safe
        one_click_updatable = self._one_click_updatable_unlocked(
            outcome['update'], outcome['remove'])

        GLib.idle_add(self.updates_available,
                      outcome['update'], update_atoms,
                      outcome['remove'], remove_atoms,
                      one_click_updatable)

    def _one_click_updatable_unlocked(self, update, remove):
        """
        Determine whether it's possible to safely execute a
        One Click Update of the system. This method will use
        some euristics (maybe not in the currently implemented
        version however) to determine if it's safe to do so.
        """
        enabled = self._one_click_updatable_kernel(update, remove)
        if not enabled:
            return False

        return True

    def _one_click_updatable_kernel(self, _update, _remove):
        """
        Determine whether One Click Update can be run basing
        on the current running kernel state and its availability
        inside repositories.
        """
        switcher = kswitch.KernelSwitcher(self._entropy)
        try:
            package_id = switcher.running_kernel_package()
        except kswitch.CannotFindRunningKernel:
            package_id = -1

        # two cases here:
        # 1. the running kernel is not installed.
        #    In this case, we cannot safely determine what kernel
        #    the user is using and thus, we will forcibly disable OCU.
        # 2. the running kernel is installed.
        #    In this case, we need to make sure that the kernel is
        #    still available in the repositories, because we don't
        #    want to allow OCU if the kernel should be bumped to a new
        #    version.
        if package_id == -1:
            write_output("_one_click_updatable_kernel: not installed",
                         debug=True)
            return False

        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():
            key_slot = inst_repo.retrieveKeySlotAggregated(package_id)
            if key_slot is None:
                write_output("_one_click_updatable_kernel: corrupted entry",
                             debug=True)
                return False

        repo_package_id, _repository_id = self._entropy.atom_match(key_slot)
        if repo_package_id == -1:
            write_output(
                "_one_click_updatable_kernel: %s not available" % (key_slot,),
                debug=True)
            return False

        return True

    def _update_repositories(self, repositories, force, activity, pid,
                             authorized=False):
        """
        Repositories Update execution code.
        """
        if not authorized:
            authorized = self._authorize(
                pid, PolicyActions.UPDATE_REPOSITORIES)
        if not authorized:
            write_output("_update_repositories: not authorized",
                         debug=True)
            try:
                self._unbusy(activity)
            except ActivityStates.AlreadyAvailableError:
                write_output("_update_repositories._unbusy: already "
                             "available, wtf !?!?")
                # wtf??
            GLib.idle_add(
                self.activity_progress, activity, 100)
            GLib.idle_add(
                self.activity_completed, activity, False)
            GLib.idle_add(
                self.repositories_updated, 401, _("Not authorized"))
            return

        with self._activity_mutex:

            # ask clients to release their locks
            self._enable_stdout_stderr_redirect()
            result = 500
            msg = ""
            self._acquire_exclusive(activity)
            try:
                self._close_local_resources()
                self._entropy_setup()
                GLib.idle_add(
                    self.activity_started, activity)
                GLib.idle_add(
                    self.activity_progress, activity, 0)

                with self._rwsem.reader():
                    if not repositories:
                        repositories = list(
                            SystemSettings()['repositories']['available'])

                    write_output("_update_repositories(): %s" % (
                            repositories,), debug=True)

                    with self._inhibit_shutdown(activity):
                        updater = self._entropy.Repositories(
                            repositories, force = force)
                        result = updater.sync()

            except AttributeError as err:
                write_output("_update_repositories error: %s" % (err,))
                result = 1
                msg = _("No repositories configured")
                return
            except Exception as err:
                write_output("_update_repositories error 2: %s" % (err,))
                result = 2
                msg = _("Unhandled Exception")
                return

            finally:
                self._disable_stdout_stderr_redirect()
                try:
                    self._unbusy(activity)
                except ActivityStates.AlreadyAvailableError:
                    write_output("_update_repositories._unbusy: already "
                                 "available, wtf !?!?")
                    # wtf??
                self._release_exclusive(activity)
                GLib.idle_add(
                    self.activity_progress, activity, 100)
                GLib.idle_add(
                    self.activity_completed, activity, result == 0)
                GLib.idle_add(
                    self.repositories_updated, result, msg)

    def _maybe_setup_package_repository(self, app_item):
        """
        Setup the Entropy Repository for the Application in
        the ActionQueueItem if path() is valid.
        """
        path = app_item.path()
        if app_item.action() == AppActions.INSTALL \
                and path is not None:
            write_output("_maybe_setup_package_repository: "
                         "this is a package file, generating "
                         "repo", debug=True)

            with self._rwsem.writer():
                try:
                    pkg_matches = self._entropy.add_package_repository(
                        path)
                    return pkg_matches, True
                except EntropyPackageException as err:
                    write_output("_maybe_setup_package_repository: "
                                 "invalid package file, "
                                 "%s" % (err,), debug=True)
                    return None, False
                except Exception as err:
                    write_output("_maybe_setup_package_repository: "
                                 "error during repository setup (err), "
                                 "%s" % (repr(err),), debug=True)
                    return None, False

        return None, True

    def _maybe_dismantle_package_repository(self, pkg_matches):
        """
        Dismantle the Entropy Repository previously configured
        by _maybe_setup_package_repository()
        """
        repository_ids = set((x[1] for x in pkg_matches))
        write_output(
            "_maybe_dismantle_package_repository: "
            "about to acquire rwsem for %s" % (pkg_matches,),
            debug=True)

        with self._rwsem.writer():
            write_output(
                "_maybe_dismantle_package_repository: "
                "acquired rwsem for %s" % (pkg_matches,),
                debug=True)
            for repository_id in repository_ids:
                try:
                    self._entropy.remove_repository(repository_id)
                except Exception as err:
                    write_output(
                        "_maybe_dismantle_package_repository: "
                        "error during repository removal (err), "
                        "%s" % (repr(err),), debug=True)


    def _action_queue_worker_thread(self):
        """
        Worker thread that handles Application Action requests
        from Rigo Clients.
        """
        while True:

            acquired = self._action_queue_waiter.acquire(False)
            if not acquired:
                # this means that the queue is empty, and
                # we can turn off the activity interruption signal
                self._interrupt_activity = False
                self._action_queue_waiter.acquire() # CANBLOCK
            if self._stop_signal:
                write_output("_action_queue_worker_thread: bye bye!",
                             debug=True)
                # bye bye!
                break

            try:
                with self._action_queue_mutex:
                    item = self._action_queue.popleft()
            except IndexError:
                # no more items
                write_output("_action_queue_worker_thread: "
                             "empty pop", debug=True)
                break

            # change execution authorization
            if self._interrupt_activity:
                item.set_authorized(False)

            write_output("_action_queue_worker_thread: "
                         "got: %s" % (item,), debug=True)

            # now execute the action
            with self._activity_mutex:
                try:
                    self._action_queue_worker_unlocked(item)
                except Exception as exc:
                    # be fault tolerant wrt exceptions
                    try:
                        write_output("_action_queue_worker_thread"
                                     ", dirty exception: "
                                     "%s, type: %s" % (exc, type(exc),))
                        t_back = entropy.tools.get_traceback()
                        if t_back:
                            write_output(t_back)
                    except Exception as exc:
                        write_output("_action_queue_worker_thread"
                                     ", failed to print exception: "
                                     "%s" % (repr(exc),))

    def _read_app_management_notes(self):
        """
        Read Application Management Install notes
        (stdout and stderr capture).
        """
        # before unbusy, read App Management Notes
        with self._app_mgmt_mutex:
            # 0o644
            perms = stat.S_IREAD | stat.S_IWRITE \
                | stat.S_IRGRP | stat.S_IROTH

            fobj = self._app_mgmt_notes['fobj']
            app_log_path = self._app_mgmt_notes['path']
            if fobj is not None:
                try:
                    fobj.close()
                except OSError as err:
                    write_output(
                        "_read_app_management_notes: "
                        "unexpected close() error %s" % (
                            repr(err),))
                self._app_mgmt_notes['fobj'] = None

            # root is already owning it
            if app_log_path is not None:
                try:
                    os.chmod(app_log_path, perms)
                except OSError as err:
                    if err.errno == errno.ENOENT:
                        # wtf, file vanished?
                        app_log_path = ""
                    elif err.errno == errno.EPERM:
                        # somebody changed the permissions
                        app_log_path = ""
                    else:
                        write_output(
                            "_read_app_management_notes: "
                            "unexpected error %s" % (repr(err),))
                        app_log_path = ""
            else:
                write_output(
                    "_read_app_management_notes: "
                    "unexpected app_log_path, None??")
                app_log_path = ""

            return app_log_path

    def _action_queue_worker_unlocked(self, item):
        """
        Action Queue worker code.
        """
        def _action_queue_finally(activity, outcome):
            if item.authorized():
                with self._action_queue_length_mutex:
                    self._action_queue_length -= 1
            self._disable_stdout_stderr_redirect()

            with self._enqueue_action_busy_hold_sem:
                # unbusy?
                has_more = self._action_queue_waiter.acquire(False)
                if has_more:
                    # put it back
                    self._action_queue_waiter.release()
                else:
                    self._maybe_signal_preserved_libraries()

                    # Clear Source Package Manager resources, do
                    # it before releasing any locks here or
                    # we may trigger an unlikely but possible race
                    try:
                        spm = self._entropy.Spm()
                        spm.clear()
                    except Exception as err:
                        write_output("_action_queue_worker_thread: "
                                     "unexpected error clearing SPM resources: "
                                     "%s" % (repr(err),))

                    # Also make sure to clear local Entropy repository caches
                    for repository_id in self._entropy.repositories():
                        try:
                            repo = self._entropy.open_repository(repository_id)
                        except RepositoryError:
                            continue
                        repo.clearCache()

                    # Clear installed packages repository cache as well
                    inst_repo = self._entropy.installed_repository()
                    with inst_repo.shared():
                        inst_repo.clearCache()

                    try:
                        app_log_path = self._read_app_management_notes()
                    except Exception as err:
                        write_output("_action_queue_worker_thread: "
                                     "unexpected error reading app mgmt notes "
                                     "%s" % (repr(err),))
                        app_log_path = ""
                    try:
                        self._unbusy(activity)
                    except ActivityStates.AlreadyAvailableError:
                        write_output("_action_queue_worker_thread"
                                     "._unbusy: already "
                                     "available, wtf !?!?")
                            # wtf??

                    self._release_shared()
                    success = outcome == AppTransactionOutcome.SUCCESS
                    write_output("_action_queue_worker_thread"
                                 "._action_queue_finally: "
                                 "outcome: %s" % (outcome,),
                                 debug=True)
                    GLib.idle_add(
                        self.activity_completed, activity, success)
                    GLib.idle_add(
                        self.applications_managed, outcome, app_log_path)
                    self._maybe_signal_configuration_updates()

        is_app = True
        if isinstance(item, RigoDaemonService.ActionQueueItem):
            activity = ActivityStates.MANAGING_APPLICATIONS
        elif isinstance(item, RigoDaemonService.UpgradeActionQueueItem):
            activity = ActivityStates.UPGRADING_SYSTEM
            is_app = False
        else:
            raise AssertionError("wtf?")

        outcome = AppTransactionOutcome.INTERNAL_ERROR
        self._enable_stdout_stderr_redirect()
        try:

            if not item.authorized():
                # then return Permission Denined
                outcome = AppTransactionOutcome.PERMISSION_DENIED
                return

            self._acquire_shared()
            self._close_local_resources()
            self._entropy_setup()
            GLib.idle_add(
                self.activity_started, activity)

            write_output("_action_queue_worker_thread: "
                         "doing %s" % (
                    item,), debug=True)

            # Package file installation support
            generated = True
            if is_app:
                pkg_matches, generated = \
                    self._maybe_setup_package_repository(item)
            if not generated:
                outcome = AppTransactionOutcome.INSTALL_ERROR
                return

            try:
                with self._rwsem.reader(), self._inhibit_shutdown(activity):
                    outcome = self._process_action(item, activity, is_app)
                    write_output("_action_queue_worker_thread, "
                                 "returned outcome: %s" % (
                            outcome,), debug=True)
            finally:
                if is_app and pkg_matches:
                    self._maybe_dismantle_package_repository(pkg_matches)

        finally:
            _action_queue_finally(activity, outcome)

    def _process_action(self, item, activity, is_app):
        """
        This is the real Application Action processing function.
        """
        if is_app:
            package_id, repository_id = item.pkg
            action = item.action()
            path = item.path()
        else:
            # upgrade
            package_id, repository_id = None, None
            action = None
            path = None
        simulate = item.simulate()

        self._txs.reset()

        outcome = AppTransactionOutcome.INTERNAL_ERROR
        try:
            item.set_parent(True)
            self._txs.set_parent(item)

            if is_app:
                if action == AppActions.REMOVE:
                    if path is not None:
                        # error, cannot remove an app from
                        # package path
                        return outcome
                    outcome = self._process_remove_action(
                        activity, action, simulate,
                        package_id, repository_id)
                elif action == AppActions.INSTALL:
                    outcome = self._process_install_action(
                        activity, action, simulate,
                        package_id, repository_id, path)
            else:
                # upgrade
                outcome = self._process_upgrade_action(
                    activity, simulate)
            return outcome

        finally:
            item.set_parent(False)
            self._txs.reset()

    def _process_upgrade_action(self, activity, simulate):
        """
        Process System Upgrade Action.
        """
        outcome = AppTransactionOutcome.INTERNAL_ERROR
        GLib.idle_add(
            self.activity_progress, activity, 0)
        try:

            outcome = self._process_upgrade_merge_action(
                activity, simulate)
            if outcome != AppTransactionOutcome.SUCCESS:
                return outcome

            # check if we need to respawn the upgrade process again?
            outcome = self._process_upgrade_action_calculate()
            if outcome is None:
                return AppTransactionOutcome.INTERNAL_ERROR

            update = outcome['update']
            if update:
                GLib.idle_add(
                    self.restarting_system_upgrade, len(update))
                outcome = self._process_upgrade_merge_action(
                    activity, simulate)
                if outcome != AppTransactionOutcome.SUCCESS:
                    return outcome

            manual_remove, remove = \
                self._entropy.calculate_orphaned_packages()
            if manual_remove or remove:
                GLib.idle_add(
                    self.unsupported_applications,
                    manual_remove, remove)

            if update:
                GLib.idle_add(self.system_restart_needed)

            return AppTransactionOutcome.SUCCESS

        finally:
            write_output("_process_upgrade_action, finally, "
                         "outcome: %s" % (
                    outcome,), debug=True)
            GLib.idle_add(
                self.activity_progress, activity, 100)

    def _process_upgrade_action_calculate(self):
        """
        Calculate Application Updates.
        """
        try:
            return self._entropy.calculate_updates()
        except SystemDatabaseError as sde:
            write_output(
                "_process_upgrade_action_calculate, SystemDatabaseError: "
                "%s" % (sde,))
            return None

    def _process_upgrade_merge_action(self, activity, simulate):
        """
        Execute the actual System Upgrade activity.
        """
        write_output(
            "_process_upgrade_merge_action, about to calculate_updates()",
            debug=True)

        outcome = self._process_upgrade_action_calculate()
        if outcome is None:
            return AppTransactionOutcome.INTERNAL_ERROR

        relaxed = False
        # per specifications, if critical_found is True, relaxed
        # must be forced to True.
        if outcome['critical_found']:
            relaxed = True

        try:
            install, _removal = self._entropy.get_install_queue(
                outcome['update'], False, False, relaxed=relaxed)

        except DependenciesNotFound as dnf:
            write_output(
                "_process_upgrade_merge_action, DependenciesNotFound: "
                "%s" % (dnf,))
            outcome = \
                AppTransactionOutcome.DEPENDENCIES_NOT_FOUND_ERROR
            return outcome

        except DependenciesCollision as dcol:
            write_output(
                "_process_upgrade_merge_action, DependenciesCollision: "
                "%s" % (dcol,))
            outcome = \
                AppTransactionOutcome.DEPENDENCIES_COLLISION_ERROR
            return outcome

        validated = self._process_install_disk_size_check(
            install)
        if not validated:
            outcome = \
                AppTransactionOutcome.DISK_FULL_ERROR
            return outcome

        # mark transactions
        for _package_id, _repository_id in install:
            self._txs.set(_package_id, _repository_id,
                          AppActions.INSTALL)

        # Download
        count, total, outcome = \
            self._process_install_fetch_action(
                install, activity)
        if outcome != AppTransactionOutcome.SUCCESS:
            return outcome

        # Install
        outcome = self._process_install_merge_action(
            install, activity, AppActions.INSTALL, simulate,
            count, total)
        return outcome

    def _process_remove_action(self, activity, action, simulate,
                               package_id, repository_id):
        """
        Process Application Remove Action.
        """
        GLib.idle_add(
            self.activity_progress, activity, 0)

        outcome = AppTransactionOutcome.INTERNAL_ERROR
        pkg_match = (package_id, repository_id)
        GLib.idle_add(
            self.activity_progress, activity, 0)
        self._txs.set(package_id, repository_id, AppActions.REMOVE)

        GLib.idle_add(
            self.processing_application,
            package_id, repository_id,
            AppActions.REMOVE,
            AppTransactionStates.MANAGE)

        try:

            write_output(
                "_process_remove_action, about to get_reverse_queue(): "
                "%s, %s" % (package_id, repository_id,), debug=True)

            try:
                removal = self._entropy.get_reverse_queue(
                    [pkg_match])

            except DependenciesNotRemovable as dnr:
                write_output(
                    "_process_remove_action, DependenciesNotRemovable: "
                    "%s" % (dnr,))
                outcome = \
                    AppTransactionOutcome.DEPENDENCIES_NOT_REMOVABLE_ERROR
                return outcome

            # mark transactions
            for _package_id, _repository_id in removal:
                self._txs.set(_package_id, _repository_id,
                              action)

            # Remove
            outcome = self._process_remove_merge_action(
                removal, activity, action, simulate)
            return outcome

        finally:
            write_output("_process_remove_action, finally, "
                         "action: %s, outcome: %s" % (
                    action, outcome,), debug=True)
            GLib.idle_add(self.application_processed,
                package_id, repository_id, action, outcome)
            GLib.idle_add(
                self.activity_progress, activity, 100)

    def _process_remove_merge_action(self, removal_queue, activity,
                                      action, simulate):
        """
        Process Applications Remove Merge Action.
        """

        def _signal_merge_process(_package_id, _repository_id, amount):
            GLib.idle_add(
                self.application_processing_update,
                _package_id, _repository_id,
                AppTransactionStates.MANAGE, amount)

        count = 0
        total = len(removal_queue)
        action_factory = self._entropy.PackageActionFactory()

        try:
            for pkg_match in removal_queue:

                package_id, repository_id = pkg_match

                write_output(
                    "_process_install_merge_action: "
                    "%s, count: %s, total: %s" % (
                        pkg_match, (count + 1),
                        total),
                    debug=True)

                # signal progress
                count += 1
                progress = int(round(float(count) / total * 100, 0))
                GLib.idle_add(
                    self.activity_progress, activity, progress)

                pkg = None
                try:
                    pkg = action_factory.get(
                        action_factory.REMOVE_ACTION,
                        (package_id, repository_id))

                    msg = "-- %s" % (purple(_("Application Removal")),)
                    self._entropy.output(msg, count=(count, total),
                                         importance=1, level="info")

                    GLib.idle_add(
                        self.processing_application,
                        package_id, repository_id, action,
                        AppTransactionStates.MANAGE)
                    _signal_merge_process(package_id, repository_id, 50)

                    if simulate:
                        # simulate time taken
                        time.sleep(5.0)
                        rc = 0
                    else:
                        rc = pkg.start()
                    if rc != 0:
                        self._txs.unset(package_id, repository_id)
                        _signal_merge_process(
                            package_id, repository_id, -1)

                        outcome = AppTransactionOutcome.REMOVE_ERROR
                        GLib.idle_add(
                            self.application_processed,
                            package_id, repository_id, action,
                            outcome)

                        write_output(
                            "_process_remove_merge_action: "
                            "%s, count: %s, total: %s, error: %s" % (
                                pkg_match, count,
                                total, rc))
                        return outcome
                finally:
                    if pkg is not None:
                        pkg.finalize()

                write_output(
                    "_process_remove_merge_action: "
                    "%s, count: %s, total: %s, done." % (
                        pkg_match, count, total), debug=True)

                # Remove us from the ongoing transactions
                self._txs.unset(package_id, repository_id)

                _signal_merge_process(package_id, repository_id, 100)

                GLib.idle_add(
                    self.application_processed,
                    package_id, repository_id, action,
                    AppTransactionOutcome.SUCCESS)

            outcome = AppTransactionOutcome.SUCCESS
            return outcome

        finally:
            write_output(
                "_process_remove_merge_action: "
                "count: %s, total: %s, finally stmt." % (
                    count, total), debug=True)

    def _maybe_enqueue_kernel_switcher_actions(self, simulate, package_id,
                                               repository_id, path):
        """
        Determine if the Application being processed for install is
        a kernel binary package. If so, use kswitch to enqueue more
        ActionQueueItems.
        """
        # it doesn't make sense to support kswitch for pkg installs.
        if path is not None:
            return

        pkg_match = (package_id, repository_id)

        # determine if key+slot is already installed, if so, there
        # is no need to trigger kernel-switcher
        repo = self._entropy.open_repository(repository_id)
        keyslot = repo.retrieveKeySlotAggregated(package_id)
        if keyslot is None:
            write_output(
                "_maybe_enqueue_kernel_switcher_actions: entry broken "
                "for package match: %s" % (pkg_match,),
            debug=True)
            return

        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():
            inst_pkg_id, _rc = inst_repo.atomMatch(keyslot)
            if inst_pkg_id != -1:
                # kernel is already installed, not triggering kswitch
                write_output(
                    "_maybe_enqueue_kernel_switcher_actions: kernel "
                    "%s already installed" % (keyslot,),
                debug=True)
                return

        switcher = kswitch.KernelSwitcher(self._entropy)

        kernel_matches = set(switcher.list())
        if pkg_match not in kernel_matches:
            # not a kernel package
            return

        write_output(
            "_maybe_enqueue_kernel_switcher_actions: found kernel "
            "binary package: %s" % (pkg_match,),
            debug=True)

        def fake_installer(_entropy_client, _matches):
            return 0

        prepared_s = switcher.prepared_switch(
            pkg_match, fake_installer, from_running=False)

        if simulate:
            write_output(
                "_maybe_enqueue_kernel_switcher_actions: "
                "simulation complete.",
                debug=True)
            return

        try:
            prepared_s.pre()
        except kswitch.CannotFindRunningKernel as cfrk:
            write_output(
                "_maybe_enqueue_kernel_switcher_actions: cannot find "
                "running kernel: %s" % (cfrk,),
                debug=True)
            return

        pkg_matches = prepared_s.get_queue()
        if not pkg_matches:
            write_output(
                "_maybe_enqueue_kernel_switcher_actions: nothing in the queue",
                debug=True)
            return

        for pkg_match in pkg_matches:
            pkg_id, pkg_repo = pkg_match
            repo = self._entropy.open_repository(pkg_repo)
            atom = repo.retrieveAtom(pkg_id)
            write_output(
                "_maybe_enqueue_kernel_switcher_actions: enqueueing %s, %s" % (
                    pkg_match, atom,),
                debug=True)

        return pkg_matches, prepared_s.post

    def _process_install_action(self, activity, action, simulate,
                                package_id, repository_id, path):
        """
        Process Application Install Action.
        """
        outcome = AppTransactionOutcome.INTERNAL_ERROR
        pkg_match = (package_id, repository_id)
        GLib.idle_add(
            self.activity_progress, activity, 0)
        self._txs.set(package_id, repository_id, AppActions.INSTALL)
        # initial transaction state is always download
        GLib.idle_add(
            self.processing_application,
            package_id, repository_id,
            AppActions.INSTALL,
            AppTransactionStates.DOWNLOAD)

        hooks_callbacks_post = []
        hooks_install = []

        ks_data = self._maybe_enqueue_kernel_switcher_actions(
            simulate, package_id, repository_id, path)

        if ks_data is not None:
            s_install, s_post = ks_data
            hooks_callbacks_post.append(s_post)
            hooks_install.extend(
                [x for x in s_install if x not in hooks_install])

        try:

            write_output(
                "_process_install_action, about to get_install_queue(): "
                "%s, %s" % (package_id, repository_id,), debug=True)

            try:
                install, _removal = self._entropy.get_install_queue(
                    [pkg_match], False, False)

            except DependenciesNotFound as dnf:
                write_output(
                    "_process_install_action, DependenciesNotFound: "
                    "%s" % (dnf,))
                # this should never happen since client executes this
                # before us
                outcome = \
                    AppTransactionOutcome.DEPENDENCIES_NOT_FOUND_ERROR
                return outcome

            except DependenciesCollision as dcol:
                write_output(
                    "_process_install_action, DependenciesCollision: "
                    "%s" % (dcol,))
                # this should never happen since client executes this
                # before us
                outcome = \
                    AppTransactionOutcome.DEPENDENCIES_COLLISION_ERROR
                return outcome

            # O(nm)
            install.extend([x for x in hooks_install if x not in install])

            validated = self._process_install_disk_size_check(
                install)
            if not validated:
                outcome = \
                    AppTransactionOutcome.DISK_FULL_ERROR
                return outcome

            # mark transactions
            for _package_id, _repository_id in install:
                self._txs.set(_package_id, _repository_id,
                              action)

            # Download
            count, total, outcome = \
                self._process_install_fetch_action(
                    install, activity)
            if outcome != AppTransactionOutcome.SUCCESS:
                return outcome

            # this way if an exception is raised in
            # _process_install_merge_action we will signal an error
            outcome = AppTransactionOutcome.INTERNAL_ERROR
            # Install
            outcome = self._process_install_merge_action(
                install, activity, action, simulate, count, total)

            if outcome == AppTransactionOutcome.SUCCESS:
                for callback in hooks_callbacks_post:
                    write_output(
                        "_process_install_action, executing callback "
                        "%s" % (callback,), debug=True)
                    if not simulate:
                        callback()
                    write_output(
                        "_process_install_action, callback complete"
                        "%s" % (callback,), debug=True)

            return outcome

        finally:
            write_output("_process_install_action, finally, "
                         "action: %s, outcome: %s" % (
                    action, outcome,), debug=True)
            GLib.idle_add(
                self.application_processed,
                package_id, repository_id, action, outcome)
            GLib.idle_add(
                self.activity_progress, activity, 100)

    def _process_install_disk_size_check(self, install_queue):
        """
        Determine if the filesystem has enough space to download and
        unpack packages to disk.
        Return true if enough space is found.
        """
        def _account_package_size(down_url, pkg_size):
            # if the package is already downloaded, don't account this part
            down_path = PackageAction.get_standard_fetch_disk_path(down_url)
            try:
                f_size = entropy.tools.get_file_size(down_path)
            except (OSError, IOError):
                return pkg_size
            pkg_size -= f_size
            return pkg_size

        download_size = 0
        unpack_size = 0
        for pkg_id, pkg_repo in install_queue:
            splitdebug = PackageAction.splitdebug_enabled(
                self._entropy, (pkg_id, pkg_repo))
            repo = self._entropy.open_repository(pkg_repo)

            # package size and unpack size calculation
            down_url = repo.retrieveDownloadURL(pkg_id)
            pkg_size = repo.retrieveSize(pkg_id)
            unpack_size += pkg_size
            pkg_size = _account_package_size(
                down_url, pkg_size)
            extra_downloads = repo.retrieveExtraDownload(pkg_id)
            for extra_download in extra_downloads:
                if not splitdebug and (extra_download['type'] == "debug"):
                    continue
                extra_pkg_size = extra_download['size']
                unpack_size += extra_pkg_size
                pkg_size += _account_package_size(
                    extra_download['download'],
                    extra_pkg_size)
            download_size += pkg_size

        # check unpack
        unpack_size = unpack_size * 1.5 # more likely...
        target_dir = etpConst['entropyunpackdir']
        while not os.path.isdir(target_dir):
            target_dir = os.path.dirname(target_dir)
        if not entropy.tools.check_required_space(
            target_dir, unpack_size):
            write_output(
                "_process_install_disk_size_check: "
                "not enough unpack space", debug=True)
            return False

        # check download size
        download_path = PackageAction.get_standard_fetch_disk_path("")
        while not os.path.isdir(download_path):
            download_path = os.path.dirname(download_path)
        if not entropy.tools.check_required_space(
            download_path, download_size):
            write_output(
                "_process_install_disk_size_check: "
                "not enough download space, required: %d" % (
                    download_size,), debug=True)
            return False

        return True

    def _process_install_fetch_action(self, install_queue, activity):
        """
        Process Applications Download Action.
        """
        def _signal_download_process(is_multifetch, opaque, amount):
            if is_multifetch:
                for pkg_match in opaque:
                    package_id, repository_id = pkg_match
                    GLib.idle_add(
                        self.application_processing_update,
                        package_id, repository_id,
                        AppTransactionStates.DOWNLOAD, amount)
            else:
                package_id, repository_id = opaque
                GLib.idle_add(
                    self.application_processing_update,
                    package_id, repository_id,
                    AppTransactionStates.DOWNLOAD, amount)

        def _account_downloads(is_multifetch, pkgs, download_map):
            if is_multifetch:
                for pkg_id, pkg_repo in pkgs:
                    repo = self._entropy.open_repository(pkg_repo)
                    pkg_atom = repo.retrieveAtom(pkg_id)
                    if pkg_atom:
                        obj = download_map.setdefault(pkg_repo, set())
                        obj.add(entropy.dep.dep_getkey(pkg_atom))
            else:
                pkg_id, pkg_repo = pkgs
                obj = download_map.setdefault(pkg_repo, set())
                pkg_atom = repo.retrieveAtom(pkg_id)
                if pkg_atom:
                    obj.add(entropy.dep.dep_getkey(pkg_atom))

        def _abort_check_function():
            """
            Check if the _interrupt_activity daemon flag is up and
            raise InterruptError.
            """
            if self._interrupt_activity:
                raise InterruptError("simulated")

        action_factory = self._entropy.PackageActionFactory()
        misc_settings = self._entropy.ClientSettings()['misc']

        download_map = {}
        _count = 0
        total = len(install_queue)

        queue = []
        pkg_action = action_factory.FETCH_ACTION
        is_multifetch = False
        multifetch = misc_settings.get("multifetch", 1)
        mymultifetch = multifetch
        metaopts = {
            "fetch_abort_function": _abort_check_function,
            }
        if multifetch > 1:

            start = 0

            while True:
                _list = install_queue[start:mymultifetch]
                if not _list:
                    break
                queue.append(_list)
                start += multifetch
                mymultifetch += multifetch

            queue_len = len(queue)
            total += queue_len
            pkg_action = action_factory.MULTI_FETCH_ACTION
            is_multifetch = True

        else:
            queue_len = len(install_queue)
            total += queue_len
            queue = install_queue

        try:
            for opaque in queue:

                write_output(
                    "_process_install_fetch_action: "
                    "%s, mode: %s, count: %s, total: %s" % (
                        opaque, pkg_action, (_count + 1),
                        total),
                    debug=True)

                _count += 1
                progress = int(round(float(_count) / total * 100, 0))
                GLib.idle_add(
                    self.activity_progress, activity, progress)

                pkg = None
                try:
                    pkg = action_factory.get(
                        pkg_action, opaque, opts=metaopts)

                    msg = ":: %s" % (purple(_("Application download")),)
                    self._entropy.output(msg, count=(_count, total),
                                         importance=1, level="info")

                    _signal_download_process(is_multifetch, opaque, 50)

                    rc = pkg.start()
                    if rc != 0:
                        _signal_download_process(is_multifetch, opaque, -1)
                        _outcome = AppTransactionOutcome.DOWNLOAD_ERROR
                        write_output(
                            "_process_install_fetch_action: "
                            "%s, mode: %s, count: %s, total: %s, error: %s" % (
                                opaque, pkg_action, _count,
                                total, rc))
                        return _count, total, _outcome

                    _account_downloads(is_multifetch, opaque, download_map)
                    _signal_download_process(is_multifetch, opaque, 100)
                finally:
                    if pkg is not None:
                        pkg.finalize()

                if self._interrupt_activity:
                    _outcome = AppTransactionOutcome.PERMISSION_DENIED
                    return _count, total, _outcome

        finally:
            self._record_download(download_map)

        return _count, total, AppTransactionOutcome.SUCCESS

    def _record_download(self, download_map):
        """
        Record downloaded Applications.
        """
        def _record():
            write_output(
                "_record_download._record: running",
                debug=True)
            for repository_id, pkg_keys in download_map.items():
                try:
                    webserv = get_entropy_webservice(
                        self._entropy, repository_id,
                        tx_cb=False)
                except WebService.UnsupportedService:
                    continue
                try:
                    webserv.add_downloads(
                        sorted(pkg_keys),
                        clear_available_cache=True)
                except WebService.WebServiceException as err:
                    write_output(
                        "_record_download: %s" % (repr(err),),
                        debug=True)
                    continue

        write_output(
            "_record_download: spawning",
            debug=True)
        task = ParallelTask(_record)
        task.name = "RecordDownloads"
        task.daemon = True
        task.start()

    def _process_install_merge_action(self, install_queue, activity,
                                      action, simulate, count, total):
        """
        Process Applications Install Merge Action.
        """

        def _signal_merge_process(_package_id, _repository_id, amount):
            GLib.idle_add(
                self.application_processing_update,
                _package_id, _repository_id,
                AppTransactionStates.MANAGE, amount)

        action_factory = self._entropy.PackageActionFactory()

        try:
            for pkg_match in install_queue:

                package_id, repository_id = pkg_match

                write_output(
                    "_process_install_merge_action: "
                    "%s, count: %s, total: %s" % (
                        pkg_match, (count + 1),
                        total),
                    debug=True)

                # signal progress
                count += 1
                progress = int(round(float(count) / total * 100, 0))
                GLib.idle_add(
                    self.activity_progress, activity, progress)

                pkg = None
                try:
                    pkg = action_factory.get(
                        action_factory.INSTALL_ACTION,
                        pkg_match)

                    msg = "++ %s" % (purple(_("Application Install")),)
                    self._entropy.output(msg, count=(count, total),
                                         importance=1, level="info")

                    GLib.idle_add(
                        self.processing_application,
                        package_id, repository_id, action,
                        AppTransactionStates.MANAGE)
                    _signal_merge_process(package_id, repository_id, 50)

                    if simulate:
                        # simulate time taken
                        time.sleep(5.0)
                        rc = 0
                    else:
                        rc = pkg.start()
                    if rc != 0:
                        self._txs.unset(package_id, repository_id)
                        _signal_merge_process(
                            package_id, repository_id, -1)

                        outcome = AppTransactionOutcome.INSTALL_ERROR
                        GLib.idle_add(
                            self.application_processed,
                            package_id, repository_id, action,
                            outcome)

                        write_output(
                            "_process_install_merge_action: "
                            "%s, count: %s, total: %s, error: %s" % (
                                pkg_match, count,
                                total, rc))
                        return outcome
                finally:
                    if pkg is None:
                        pkg.finalize()

                write_output(
                    "_process_install_merge_action: "
                    "%s, count: %s, total: %s, done." % (
                        pkg_match, count, total), debug=True)

                # Remove us from the ongoing transactions
                self._txs.unset(package_id, repository_id)

                _signal_merge_process(package_id, repository_id, 100)

                GLib.idle_add(
                    self.application_processed,
                    package_id, repository_id, action,
                    AppTransactionOutcome.SUCCESS)

                if self._interrupt_activity:
                    outcome = AppTransactionOutcome.PERMISSION_DENIED
                    return outcome

            outcome = AppTransactionOutcome.SUCCESS
            return outcome

        finally:
            write_output(
                "_process_install_merge_action: "
                "count: %s, total: %s, finally stmt." % (
                    count, total), debug=True)

    def _maybe_signal_preserved_libraries(self):
        """
        Signal preserved libraries if needed.
        """
        with self._rwsem.reader():
            inst_repo = self._entropy.installed_repository()
            with inst_repo.shared():
                preserved_mgr = PreservedLibraries(
                    inst_repo, None, frozenset(),
                    root=etpConst['systemroot'])
                preserved = preserved_mgr.list()

        if preserved:
            GLib.idle_add(
                self.preserved_libraries_available,
                preserved)

    def _maybe_signal_configuration_updates(self):
        """
        Signal Configuration Files Updates if needed.
        """
        scandata = self._configuration_updates(_force=True)
        if scandata:
            GLib.idle_add(
                self.configuration_updates_available,
                self._dbus_prepare_configuration_files(
                    scandata.root(), scandata))

    def _dbus_prepare_configuration_files(self, root, scandata):
        """
        Prepare the ConfigurationFiles object for sending through
        dbus.
        """
        updates = [(root, source, x['destination'], \
                    x['package_ids'], x['automerge']) for source, x \
                       in scandata.items()]
        return updates

    def _configuration_updates(self, _force=False):
        """
        Return the latest (or a new one if not initialized yet)
        ConfigurationFiles object.
        """
        with self._rwsem.reader():
            with self._config_updates_mutex:
                if self._config_updates is None or _force:
                    updates = self._entropy.ConfigurationUpdates()
                    scandata = self._enrich_configuration_updates(
                        updates.get())
                    self._config_updates = scandata
                else:
                    scandata = self._config_updates
        return scandata

    def _enrich_configuration_updates(self, scandata):
        """
        Enrich ConfigurationFiles object returned by Entropy Client
        with extended information.
        """
        _cache = {}
        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():

            for _k, v in scandata.items():
                dest = v['destination']
                pkg_ids = _cache.get(dest)

                if pkg_ids is None:
                    pkg_ids = list(inst_repo.searchBelongs(dest))
                    _cache[dest] = pkg_ids
                v['package_ids'] = pkg_ids

        return scandata

    def _close_local_resources(self):
        """
        Close any Entropy resource that might have been changed
        or replaced.
        """
        with self._rwsem.writer():
            self._close_local_resources_unlocked()

    def _close_local_resources_unlocked(self):
        """
        Same as _close_local_resources but without rwsem locking.
        """
        # close() is fine, it will be automatically reopened
        # upon request. This way we make sure to not leave
        # any transaction uncommitted. Previously, we called
        # reopen_installed_repository() which did close() + open().
        # The open() part can be avoided.
        self._entropy.close_installed_repository()
        self._entropy.close_repositories()

    def _acquire_shared(self):
        """
        Acquire Shared access to Entropy Resources.
        This method must be called with activity_mutex held
        to avoid races with _acquire_exclusive() and
        _acquire_exclusive_simple_nb().
        """
        act_acquired = self._activity_mutex.acquire(False)
        if act_acquired:
            # bug!
            self._activity_mutex.release()
            raise AttributeError(
                "_acquire_shared: "
                "Activity mutex not acquired!")
        write_output("_acquire_shared: about to acquire lock",
                     debug=True)
        self._reslock.acquire_shared()

    def _acquire_exclusive_simple_nb(self):
        """
        Acquire Exclusive access to Entropy Resources in
        non-blocking mode without asking connected
        clients to release their locks.
        This method must be called with activity_mutex held
        to avoid races with _acquire_exclusive() and
        _acquire_shared().
        """
        act_acquired = self._activity_mutex.acquire(False)
        if act_acquired:
            # bug!
            self._activity_mutex.release()
            raise AttributeError(
                "_acquire_exclusive_simple_nb: "
                "Activity mutex not acquired!")
        write_output("_acquire_exclusive_simple_nb: "
                     "about to acquire lock",
                     debug=True)

        with self._acquired_exclusive_mutex:
            if not self._acquired_exclusive:
                # now we got the exclusive lock
                acquired = self._reslock.try_acquire_exclusive()
                if acquired:
                    self._acquired_exclusive = True
                return acquired
            return True

    def _release_exclusive_simple_nb(self):
        """
        Release Exclusive access to Entropy Resources previously
        acquired through _acquire_exclusive_simple_nb().
        This method must be called with activity_mutex held
        to avoid races with _acquire_exclusive() and
        _acquire_exclusive().
        """
        write_output("_release_exclusive_simple_nb: "
                     "about to release lock",
                     debug=True)
        act_acquired = self._activity_mutex.acquire(False)
        if act_acquired:
            # bug!
            self._activity_mutex.release()
            raise AttributeError(
                "_release_exclusive_simple_nb: "
                "Activity mutex not acquired!")

        with self._acquired_exclusive_mutex:
            if self._acquired_exclusive:
                self._reslock.release()
                self._acquired_exclusive = False

    def _release_shared(self):
        """
        Release Shared access to Entropy Resources.
        This method must be called with activity_mutex held
        to avoid races with _acquire_exclusive() and
        _acquire_exclusive_simple_nb().
        """
        write_output("_release_shared: about to release lock",
                     debug=True)
        act_acquired = self._activity_mutex.acquire(False)
        if act_acquired:
            # bug!
            self._activity_mutex.release()
            raise AttributeError(
                "_acquire_shared: "
                "Activity mutex not acquired!")
        self._reslock.release()

    def _acquire_exclusive(self, activity):
        """
        Acquire Exclusive access to Entropy Resources.
        Note: this is blocking and will issue the
        exclusive_acquired() signal when done.
        This method must be called with activity_mutex held
        to avoid races with _acquire_shared() and
        _acquire_exclusive_simple_nb().
        """
        act_acquired = self._activity_mutex.acquire(False)
        if act_acquired:
            # bug!
            self._activity_mutex.release()
            raise AttributeError(
                "_acquire_exclusive: "
                "Activity mutex not acquired!")
        acquire = False
        with self._acquired_exclusive_mutex:
            if not self._acquired_exclusive:
                # now we got the exclusive lock
                self._acquired_exclusive = True
                acquire = True

        if acquire:
            write_output("_acquire_exclusive: about to acquire lock",
                         debug=True)
            acquired = self._reslock.try_acquire_exclusive()
            if not acquired:
                write_output("_acquire_exclusive: asking to unlock",
                             debug=True)
                GLib.idle_add(
                    self.resources_unlock_request, activity)
                self._reslock.acquire_exclusive()

            write_output("_acquire_exclusive: just acquired lock",
                         debug=True)

    def _release_exclusive(self, activity):
        """
        Release Exclusive access to Entropy Resources.
        """
        act_acquired = self._activity_mutex.acquire(False)
        if act_acquired:
            # bug!
            self._activity_mutex.release()
            raise AttributeError(
                "_acquire_exclusive: "
                "Activity mutex not acquired!")

        # make sure to not release locks as long
        # as there is activity
        with self._acquired_exclusive_mutex:
            if self._acquired_exclusive:
                GLib.idle_add(
                    self.resources_lock_request, activity)
                self._reslock.release()
                # now we got the exclusive lock
                self._acquired_exclusive = False

    def _entropy_setup(self):
        """
        Notify us that a new client is now connected.
        Here we reload Entropy configuration and other resources.
        """
        write_output("_entropy_setup(): called", debug=True)
        with self._rwsem.writer():
            initconfig_entropy_constants(etpConst['systemroot'])
            self._entropy.Settings().clear()
            self._entropy._validate_repositories()
            self._close_local_resources_unlocked()
        write_output("_entropy_setup(): complete", debug=True)

    def _send_greetings(self):
        """
        Send connected clients several welcome signals.
        """
        acquired = False
        try:
            acquired = self._greetings_serializer.acquire(False)
            if not acquired:
                return

            with self._activity_mutex:
                self._acquire_shared()
                try:
                    self._close_local_resources()
                    self._entropy_setup()

                    with self._rwsem.reader():
                        unavailable_repositories = \
                            self._entropy.unavailable_repositories()

                    if unavailable_repositories:
                        GLib.idle_add(
                            self.unavailable_repositories,
                                unavailable_repositories)

                    if Repository.are_repositories_old():
                        GLib.idle_add(self.old_repositories)

                    with self._rwsem.reader():
                        self._installed_repository_updated_unlocked()

                    self._maybe_signal_noticeboards_available_unlocked()

                finally:
                    self._release_shared()
        finally:
            if acquired:
                self._greetings_serializer.release()

    def _maybe_signal_noticeboards_available_unlocked(self):
        """
        Unlocked version (no shared nor exclusive Entropy
        Resources Lock acquired, no activity mutex acquired)
        of _maybe_signal_noticeboards_available()
        """
        with self._rwsem.reader():
            notices = []
            for repository in self._entropy.repositories():
                nb = NoticeBoard(repository)

                try:
                    notice = nb.data()
                except KeyError:
                    notice = None
                if not notice:
                    continue

                notices.append((repository, notice))

        if notices:
            GLib.idle_add(
                self.noticeboards_available,
                self._dbus_prepare_noticeboard_metadata(
                    notices)
                )

    def _maybe_signal_noticeboards_available(self):
        """
        Signal (as soon as RigoDaemon can) the availability
        of NoticeBoards among configured repositories.
        """
        with self._activity_mutex:
            self._acquire_shared()
            try:
                self._close_local_resources()
                self._entropy_setup()
                self._maybe_signal_noticeboards_available_unlocked()
            finally:
                self._release_shared()

    def _dbus_prepare_noticeboard_metadata(self, notices):
        """
        Prepare Notice Board repositories metadata for sending
        through dbus.
        """
        outcome = []
        for repository, notice in notices:
            for notice_id, data in notice.items():
                obj = (repository, notice_id,
                       data['guid'],
                       data['link'], data['title'],
                       data['description'],
                       data['pubDate'])
                outcome.append(obj)
        return outcome

    def _optimize_mirrors(self, repository_ids):
        """
        Execute a background Repository Mirrors optimization.
        This low-priority method shall reorder Repository mirrors
        basing on throughput performance.
        It can be run in parallel with any other Entropy Client
        activity since the operation is atomic.
        """
        optimized = False
        for repository_id in repository_ids:

            write_output("_optimize_mirrors: %s" % (
                    repository_id,), debug=True)

            try:
                repository_metadata = self._entropy.reorder_mirrors(
                    repository_id)
            except KeyError as err:
                write_output("_optimize_mirrors: "
                             "repository update error: %s" % (
                        repr(err),), debug=True)
                continue

            optimized = True
            mirrors = repository_metadata.get('plain_packages')
            write_output("_optimize_mirrors: repository "
                         "'%s' updated, mirrors: %s" % (
                    repository_id, mirrors), debug=True)

        GLib.idle_add(self.mirrors_optimized, repository_ids, optimized)

    ### DBUS METHODS

    @dbus.service.method(BUS_NAME, in_signature='asb',
        out_signature='b', sender_keyword='sender')
    def update_repositories(self, repositories, force, sender=None):
        """
        Request RigoDaemon to update the given repositories.
        At the end of the execution, the "repositories_updated"
        signal will be raised.
        """
        pid = self._get_caller_pid(sender)
        write_output("update_repositories called: %s, client pid: %s" % (
                repositories, pid,), debug=True)

        activity = ActivityStates.UPDATING_REPOSITORIES
        try:
            self._busy(activity)
        except ActivityStates.BusyError:
            write_output("update_repositories: I'm busy", debug=True)
            # I am already busy doing other stuff, cannot
            # satisfy request
            return False
        except ActivityStates.SameError:
            write_output("update_repositories: already doing it",
                         debug=True)
            # I am already busy doing the same activity
            return False

        task = ParallelTask(self._update_repositories, repositories,
                            force, activity, pid)
        task.daemon = True
        task.name = "UpdateRepositoriesThread"
        task.start()
        return True

    def _enqueue_application_action_internal(
        self, pid, package_id, repository_id, package_path,
        action, simulate):
        """
        Internal enqueue_application_action() function.
        """
        try:
            if not package_path:
                package_path = None
            else:
                self._dbus_to_unicode(package_path)
            repository_id = self._dbus_to_unicode(repository_id)
            package_id = int(package_id)
            simulate = bool(simulate)
            action = self._dbus_to_unicode(action)

            authorized = self._authorize(
                pid, PolicyActions.MANAGE_APPLICATIONS)
            item = self.ActionQueueItem(
                package_id,
                repository_id,
                package_path,
                action,
                simulate,
                authorized)
            with self._action_queue_mutex:
                self._action_queue.append(item)
            if authorized:
                with self._action_queue_length_mutex:
                    self._action_queue_length += 1
                GLib.idle_add(
                    self.application_enqueued,
                    package_id, repository_id, action)
            self._action_queue_waiter.release()
        finally:
            self._enqueue_action_busy_hold_sem.release()

    @dbus.service.method(BUS_NAME, in_signature='isssb',
        out_signature='b', sender_keyword='sender')
    def enqueue_application_action(self, package_id, repository_id,
                                   package_path, action,
                                   simulate, sender=None):
        """
        Request RigoDaemon to enqueue a new Application Action, if
        possible.
        """
        pid = self._get_caller_pid(sender)
        write_output("enqueue_application_action called: "
                     "%s, %s, client pid: %s" % (
                (package_id, repository_id, package_path),
                action, pid), debug=True)

        self._enqueue_action_busy_hold_sem.acquire()
        try:
            activity = ActivityStates.MANAGING_APPLICATIONS
            busied = False
            try:
                self._busy(activity)
                busied = True
            except ActivityStates.BusyError:
                # I am already busy doing other stuff, cannot
                # satisfy request
                self._enqueue_action_busy_hold_sem.release()
                return False
            except ActivityStates.SameError:
                # I am already busy doing this, so just enqueue
                write_output("enqueue_application_action: "
                             "already busy, just enqueue",
                             debug=True)

            if busied:
                # Setup Application Management
                # Install/Remove notes
                tmp_fd, tmp_path = const_mkstemp(
                    prefix="RigoDaemonAppMgmt",
                    suffix=".notes")
                with self._app_mgmt_mutex:
                    fobj = self._app_mgmt_notes['fobj']
                    path = self._app_mgmt_notes['path']
                    if fobj is not None:
                        try:
                            fobj.close()
                        except (OSError, IOError):
                            write_output(
                                "enqueue_application_action: "
                                "busied, but cannot close previous fd")
                    if path is not None:
                        try:
                            os.remove(path)
                        except (OSError, IOError):
                            write_output(
                                "enqueue_application_action: "
                                "busied, but cannot remove previous path")
                    try:
                        fobj = os.fdopen(tmp_fd, "w")
                    except OSError as err:
                        write_output(
                            "enqueue_application_action: "
                            "cannot open tmp_fd: %s" % (repr(err),))
                        fobj = None
                    self._app_mgmt_notes['fobj'] = fobj
                    self._app_mgmt_notes['path'] = tmp_path

            task = ParallelTask(
                self._enqueue_application_action_internal,
                pid, package_id, repository_id, package_path,
                action, simulate)
            task.name = "EnqueueApplicationActionThread"
            task.daemon = True
            task.start()
            # keeping the sem down
            return True

        except Exception:
            self._enqueue_action_busy_hold_sem.release()
            raise

    @dbus.service.method(BUS_NAME, in_signature='b',
        out_signature='b', sender_keyword='sender')
    def upgrade_system(self, simulate, sender=None):
        """
        Request RigoDaemon to Upgrade the whole System.
        """
        pid = self._get_caller_pid(sender)
        write_output("upgrade_system called: "
                     "simulate: %s, client pid: %s" % (
                (simulate, pid,)), debug=True)

        self._enqueue_action_busy_hold_sem.acquire()
        try:
            activity = ActivityStates.UPGRADING_SYSTEM
            try:
                self._busy(activity)
            except ActivityStates.BusyError:
                # I am already busy doing other stuff, cannot
                # satisfy request
                self._enqueue_action_busy_hold_sem.release()
                return False
            except ActivityStates.SameError:
                # I am already busy doing this
                write_output("upgrade_system: "
                             "already doing it, failing",
                             debug=True)
                self._enqueue_action_busy_hold_sem.release()
                return False

            def _enqueue():
                try:
                    authorized = self._authorize(
                        pid, PolicyActions.UPGRADE_SYSTEM)
                    item = self.UpgradeActionQueueItem(
                        bool(simulate), authorized)
                    with self._action_queue_mutex:
                        self._action_queue.append(item)
                    if authorized:
                        with self._action_queue_length_mutex:
                            self._action_queue_length += 1
                    self._action_queue_waiter.release()
                finally:
                    self._enqueue_action_busy_hold_sem.release()

            task = ParallelTask(_enqueue)
            task.name = "UpgradeSystemThread"
            task.daemon = True
            task.start()
            # keeping the sem down
            return True

        except Exception:
            self._enqueue_action_busy_hold_sem.release()
            raise

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def interrupt_activity(self):
        """
        Interrupt any ongoing Activity
        """
        write_output("interrupt_activity called", debug=True)
        self._interrupt_activity = True

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='i')
    def activity(self):
        """
        Return RigoDaemon activity states (any of RigoDaemon.ActivityStates
        values).
        """
        write_output("activity called", debug=True)
        return self._current_activity

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='i')
    def action_queue_length(self):
        """
        Return the current size of the Application Action Queue.
        """
        write_output("action_queue_length called", debug=True)
        # might temporarily go to -1 ?
        return max(0, self._action_queue_length)

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='a(isssba(iss))')
    def action_queue_items(self):
        """
        Return a list of Applications that are currently on the
        execution queue.
        """
        write_output("action_queue_items called", debug=True)
        parent = None
        items = []

        with self._action_queue_mutex:
            write_output("action_queue_items mutex acquired", debug=True)
            with self._txs:
                write_output("action_queue_items txs mutex acquired",
                             debug=True)

                parent = self._txs.get_parent()
                write_output("action_queue_items: got parent %s" % (parent,),
                             debug=True)

                if parent is not None:
                    all_txs = self._txs.all()
                    write_output("action_queue_items: got txs: %d" % (
                            len(all_txs),),
                                 debug=True)
                    items.append((parent, all_txs))
            # be fast here
            for item in self._action_queue:
                items.append((item, []))

        def _item_map(item_parent):
            item, children = item_parent
            if isinstance(item, RigoDaemonService.UpgradeActionQueueItem):
                return 0, "", "", item.action(), item.simulate(), children

            pkg_id, repository_id = item.pkg
            path, action, simulate = item.path(), item.action(), item.simulate()
            if path is None:
                path = ""
            return pkg_id, repository_id, path, action, \
                simulate, children

        # ha ha! now try to guess what's doing...
        items = list([x for x in map(_item_map, items) if x is not None])
        return items

    @dbus.service.method(BUS_NAME, in_signature='is',
        out_signature='s')
    def action(self, package_id, repository_id):
        """
        Return Application transaction state (AppAction enum
        value)
        """
        write_output("action called: %s, %s" % (
                package_id, repository_id,), debug=True)
        return self._txs.get(package_id, repository_id)

    @dbus.service.method(BUS_NAME, in_signature='as',
        out_signature='')
    def accept_licenses(self, names):
        """
        Accept Application Licenses.
        """
        write_output("accept_licenses called: %s" % (names,),
                     debug=True)
        def _accept():
            with self._rwsem.reader():
                inst_repo = self._entropy.installed_repository()
                # this should be exclusive(), maybe, but accepting
                # the same license twice has no side effects.
                with inst_repo.shared():
                    for name in names:
                        inst_repo.acceptLicense(name)

                    inst_repo.commit()

        task = ParallelTask(_accept)
        task.daemon = True
        task.name = "AcceptLicensesThread"
        task.start()

    @dbus.service.method(BUS_NAME, in_signature='s',
        out_signature='b', sender_keyword='sender')
    def merge_configuration(self, source, sender=None):
        """
        Move configuration file from source path over to
        destination, keeping destination path permissions.
        """
        write_output("move_configuration called: %s" % (locals(),),
                     debug=True)
        pid = self._get_caller_pid(sender)
        authenticated = self._authorize_sync(
            pid, PolicyActions.MANAGE_CONFIGURATION)
        if not authenticated:
            return False
        updates = self._configuration_updates()
        return updates.merge(source)

    @dbus.service.method(BUS_NAME, in_signature='s',
        out_signature='s', sender_keyword='sender')
    def diff_configuration(self, source, sender=None):
        """
        Generate a diff between destination -> source file paths and
        return a path containing the output to caller. If diff cannot
        be run, return empty string.
        """
        write_output("diff_configuration called: %s" % (locals(),),
                     debug=True)
        pid = self._get_caller_pid(sender)
        authenticated = self._authorize_sync(
            pid, PolicyActions.MANAGE_CONFIGURATION)
        if not authenticated:
            return ""

        updates = self._configuration_updates()
        root = updates.root()
        obj = updates.get(source)
        if obj is None:
            return ""

        uid = self._get_caller_user(sender)
        source_path = root + source
        dest_path = root + obj['destination']

        rc = None
        tmp_fd, tmp_path = None, None
        path = ""
        try:
            tmp_fd, tmp_path = const_mkstemp(
                prefix="RigoDaemon", suffix=".diff")
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                rc = subprocess.call(
                    ["/usr/bin/diff", "-Nu", dest_path, source_path],
                    stdout = tmp_f)
            if rc == os.EX_OK:
                # no differences
                pass
            elif rc == 1:
                # differences were found
                path = self._prepare_configuration_file(
                    tmp_path, uid)
            else:
                write_output("cannot diff_configuration: %s" % (
                        rc,), debug=True)

        except (OSError, IOError,) as err:
            write_output("cannot diff_configuration: %s" % (
                    repr(err),), debug=True)

        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except (OSError, IOError):
                    pass
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        return path

    def _view_configuration_file(self, source, sender, dest=False):
        """
        View a source or destination configuration file
        """
        pid = self._get_caller_pid(sender)

        authenticated = self._authorize_sync(
            pid, PolicyActions.MANAGE_CONFIGURATION)
        if not authenticated:
            return ""

        updates = self._configuration_updates()
        root = updates.root()
        obj = updates.get(source)
        if obj is None:
            return ""

        uid = self._get_caller_user(sender)
        if dest:
            source_path = root + obj['destination']
        else:
            source_path = root + source
        return self._prepare_configuration_file(source_path, uid)

    def _prepare_configuration_file(self, path, uid):
        """
        Prepare the given configuration file copying it to
        a temporary path and setting proper permissions.
        """
        tmp_fd, tmp_path = const_mkstemp(prefix="RigoDaemon")
        try:
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                with open(path, "rb") as path_f:
                    shutil.copyfileobj(path_f, tmp_f)
            # fixup perms
            os.chown(tmp_path, uid, -1)
            path = tmp_path
        except (OSError, IOError) as err:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            write_output("cannot _prepare_configuration_file: %s" % (
                    repr(err),), debug=True)
            path = ""
        return path

    def _execute_settings_management(self, pid, method, *args, **kwargs):
        """
        Execute the given configuration management task, acquiring all
        the needed locks, blocking if needed, etc.
        """
        authorized = self._authorize(
            pid, PolicyActions.MANAGE_CONFIGURATION)
        if not authorized:
            return

        with self._activity_mutex: # BLOCK
            self._acquire_shared()
            try:

                done = False
                with self._rwsem.writer():
                    done = method(*args, **kwargs)
                return done

            finally:
                self._release_shared()

    @dbus.service.method(BUS_NAME, in_signature='s',
        out_signature='s', sender_keyword='sender')
    def view_configuration_source(self, source, sender=None):
        """
        Copy configuration source file to a temporary path featuring
        caller ownership. If file cannot be copied, empty string is
        returned.
        """
        write_output("view_configuration_source called: %s" % (locals(),),
                     debug=True)
        return self._view_configuration_file(source, sender)

    @dbus.service.method(BUS_NAME, in_signature='ss',
        out_signature='b', sender_keyword='sender')
    def save_configuration_source(self, source, path, sender=None):
        """
        Save a new proposed source configuration file to the given
        source file, if exists.
        """
        write_output("save_configuration_source called: %s" % (locals(),),
                     debug=True)
        pid = self._get_caller_pid(sender)
        authenticated = self._authorize_sync(
            pid, PolicyActions.MANAGE_CONFIGURATION)
        if not authenticated:
            return False
        updates = self._configuration_updates()
        obj = updates.get(source)
        if obj is None:
            return False
        try:
            entropy.tools.rename_keep_permissions(path, source)
        except OSError as err:
            write_output("cannot save_configuration_source: %s" % (
                    repr(err),), debug=True)
            return False
        return True

    @dbus.service.method(BUS_NAME, in_signature='s',
        out_signature='s', sender_keyword='sender')
    def view_configuration_destination(self, source, sender=None):
        """
        Copy configuration destination file to a temporary path featuring
        caller ownership. If file cannot be copied, empty string is
        returned.
        """
        write_output("view_configuration_destination called: %s" % (
                locals(),),
                     debug=True)
        return self._view_configuration_file(source, sender, dest=True)

    @dbus.service.method(BUS_NAME, in_signature='s',
        out_signature='b', sender_keyword='sender')
    def discard_configuration(self, source, sender=None):
        """
        Remove configuration file from source path.
        """
        write_output("discard_configuration called: %s" % (locals(),),
                     debug=True)
        pid = self._get_caller_pid(sender)
        authenticated = self._authorize_sync(
            pid, PolicyActions.MANAGE_CONFIGURATION)
        if not authenticated:
            return False
        updates = self._configuration_updates()
        return updates.remove(source)

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='', sender_keyword='sender')
    def configuration_updates(self, sender=None):
        """
        Request RigoDaemon to signal for configuration file
        updates, if any.
        """
        write_output("configuration_updates called", debug=True)
        def _signal(pid):
            authorized = self._authorize(
                pid, PolicyActions.MANAGE_CONFIGURATION)
            if not authorized:
                return
            self._maybe_signal_configuration_updates()

        task = ParallelTask(
            _signal,
            self._get_caller_pid(sender))
        task.name = "ConfigurationUpdatesSignal"
        task.daemon = True
        task.start()

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def noticeboards(self):
        """
        Request RigoDaemon to signal for noticeboards
        data, if any.
        """
        write_output("noticeboards called", debug=True)

        task = ParallelTask(
            self._maybe_signal_noticeboards_available)
        task.name = "NoticeboardsAvailableSignal"
        task.daemon = True
        task.start()

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='', sender_keyword='sender')
    def reload_configuration_updates(self, sender=None):
        """
        Load a new ConfigurationFiles object.
        """
        write_output("reload_configuration_updates called", debug=True)
        def _reload(pid):
            authorized = self._authorize(
                pid, PolicyActions.MANAGE_CONFIGURATION)
            if not authorized:
                return

            with self._rwsem.reader():
                updates = self._entropy.ConfigurationUpdates()
                with self._config_updates_mutex:
                    scandata = updates.get()
                    self._config_updates = scandata

        task = ParallelTask(
            _reload,
            self._get_caller_pid(sender))
        task.name = "ReloadConfigurationUpdates"
        task.daemon = True
        task.start()

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='b')
    def exclusive(self):
        """
        Return whether RigoDaemon is running in with
        Entropy Resources acquired in exclusive mode.
        """
        write_output("exclusive called", debug=True)

        return self._acquired_exclusive

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='i', sender_keyword='sender')
    def api(self, sender=None):
        """
        Return RigoDaemon API version.
        """
        write_output("api called", debug=True)
        return RigoDaemonService.API_VERSION

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def reload(self):
        """
        Ask RigoDaemon to exit when no clients are
        connected in order to get loaded back by Dbus.
        """
        write_output("reload called", debug=True)
        self._activate_deferred_shutdown()

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def pong(self):
        """
        Answer to RigoDaemon ping() events to avoid
        RigoDaemon to terminate with SIGTERM.
        """
        write_output("pong() received", debug=True)

        with self._ping_timer_mutex:
            if self._ping_timer is not None:
                # stop the bomb!
                self._ping_timer.cancel()
                self._ping_timer = None

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def hello(self):
        """
        Somebody is greeting us, need to dispatch some
        welcome signals.
        """
        write_output("hello() received", debug=True)
        task = ParallelTask(self._send_greetings)
        task.name = "SendGreetings"
        task.daemon = True
        task.start()

    @dbus.service.method(BUS_NAME, in_signature='s',
        out_signature='b', sender_keyword='sender')
    def enable_repository(self, repository_id, sender=None):
        """
        Enable the given Repository.
        """
        pid = self._get_caller_pid(sender)
        write_output("enable_repository() received, pid: %s" % (pid,),
                     debug=True)

        repository_id = self._dbus_to_unicode(repository_id)
        settings = SystemSettings()
        repo_data = settings['repositories']
        available = repo_data['available']
        excluded = repo_data['excluded']
        if repository_id in available:
            write_output("enable_repository(): repository already enabled",
                         debug=True)
            return False # repository already enabled
        if repository_id not in excluded:
            write_output("enable_repository(): repository not found",
                         debug=True)
            return False # repository not available
        if not entropy.tools.validate_repository_id(repository_id):
            write_output("enable_repository(): repository string invalid",
                         debug=True)
            return False # repository_id string is invalid

        def _configure(pid):
            with self._settings_mgmt_serializer:
                def _enable_repo():
                    outcome = self._entropy.enable_repository(repository_id)
                    self._entropy.Settings().clear()
                    self._entropy._validate_repositories()
                    return outcome
                executed = self._execute_settings_management(
                    pid, _enable_repo)
                GLib.idle_add(self.repositories_settings_changed,
                              [repository_id], executed)

        task = ParallelTask(
            _configure,
            self._get_caller_pid(sender))
        task.name = "EnableRepository"
        task.daemon = True
        task.start()
        return True

    @dbus.service.method(BUS_NAME, in_signature='s',
        out_signature='b', sender_keyword='sender')
    def disable_repository(self, repository_id, sender=None):
        """
        Disable the given Repository.
        """
        pid = self._get_caller_pid(sender)
        write_output("disable_repository() received, pid: %s" % (pid,),
                     debug=True)

        repository_id = self._dbus_to_unicode(repository_id)
        settings = SystemSettings()
        repo_data = settings['repositories']
        available = repo_data['available']
        excluded = repo_data['excluded']
        if repository_id not in available:
            write_output("disable_repository(): repository already disabled",
                         debug=True)
            return False # repository already enabled
        if repository_id in excluded:
            write_output("disable_repository(): repository not available",
                         debug=True)
            return False # repository not available
        if not entropy.tools.validate_repository_id(repository_id):
            write_output("disable_repository(): repository string invalid",
                         debug=True)
            return False # repository_id string is invalid

        def _configure(pid):
            with self._settings_mgmt_serializer:
                def _disable_repo():
                    outcome = self._entropy.disable_repository(repository_id)
                    self._entropy.Settings().clear()
                    self._entropy._validate_repositories()
                    return outcome
                executed = self._execute_settings_management(
                    pid, _disable_repo)
                GLib.idle_add(self.repositories_settings_changed,
                              [repository_id], executed)

        task = ParallelTask(
            _configure,
            self._get_caller_pid(sender))
        task.name = "DisableRepository"
        task.daemon = True
        task.start()
        return True

    @dbus.service.method(BUS_NAME, in_signature='ss',
        out_signature='b', sender_keyword='sender')
    def rename_repository(self, from_repository_id, to_repository_id,
                          sender=None):
        """
        Rename a Repository.
        """
        pid = self._get_caller_pid(sender)
        write_output("disable_repository() received, pid: %s" % (pid,),
                     debug=True)

        settings = SystemSettings()
        repo_data = settings['repositories']
        available = repo_data['available']
        excluded = repo_data['excluded']
        repositories = set(available.keys())
        repositories |= set(excluded.keys())
        if from_repository_id not in repositories:
            return False
        if to_repository_id in repositories:
            return False
        if not entropy.tools.validate_repository_id(from_repository_id):
            return False # repository_id string is invalid
        if not entropy.tools.validate_repository_id(to_repository_id):
            return False # repository_id string is invalid

        def _rename_repository():
            from_data = None
            if from_repository_id in available:
                from_data = copy.copy(available[from_repository_id])
            elif from_repository_id in excluded:
                from_data = copy.copy(excluded[from_repository_id])
            else:
                return False # wtf?

            # create new repo
            from_data['repoid'] = to_repository_id
            added = self._entropy.add_repository(from_data)
            if not added:
                return False
            # remove old
            self._entropy.remove_repository(from_repository_id)
            return True

        def _configure(pid):
            with self._settings_mgmt_serializer:
                executed = self._execute_settings_management(
                    pid, _rename_repository)
                GLib.idle_add(self.repositories_settings_changed,
                              [from_repository_id, to_repository_id],
                              executed)

        task = ParallelTask(
            _configure,
            self._get_caller_pid(sender))
        task.name = "RenameRepository"
        task.daemon = True
        task.start()
        return True

    @dbus.service.method(BUS_NAME, in_signature='as',
        out_signature='b', sender_keyword='sender')
    def optimize_mirrors(self, repository_ids, sender=None):
        """
        Request RigoDaeon to optimize Repository Mirrors
        in background.
        """
        pid = self._get_caller_pid(sender)
        write_output("optimize_mirrors called: "
                     "client pid: %s" % (
                (pid,)), debug=True)

        def _optimize(_repository_ids):
            _repository_ids = [self._dbus_to_unicode(x) for \
                                  x in _repository_ids]
            authorized = self._authorize(
                pid, PolicyActions.MANAGE_CONFIGURATION)
            if authorized:
                th = ParallelTask(
                    self._optimize_mirrors,
                    _repository_ids)
                th.name = "OptimizeMirrorsThread"
                th.daemon = True
                th.start()
            else:
                GLib.idle_add(self.mirrors_optimized,
                              _repository_ids, False)

        task = ParallelTask(_optimize, repository_ids)
        task.name = "OptimizeMirrorsRequestThread"
        task.daemon = True
        task.start()
        return True

    ### DBUS SIGNALS

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='sssbisiibb')
    def output(self, _text, _header, _footer, _back, _importance, _level,
               _count_c, _count_t, _percent, _raw):
        """
        Entropy Library output text signal. Clients will be required to
        forward this message to User.
        """

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='iiiis')
    def transfer_output(self, _average, _downloaded_size,
                        _total_size, _data_transfer_bytes,
                        _time_remaining_secs):
        """
        Entropy UrlFetchers output signals. Clients will be required to
        forward this message to User in Progress Bar form.
        """

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='is')
    def repositories_updated(self, _result, _message):
        """
        Repositories have been updated.
        "result" is an integer carrying execution return status.
        """
        write_output("repositories_updated() issued, args:"
                     " %s" % (locals(),), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='ss')
    def applications_managed(self, _outcome, _app_log_path):
        """
        Enqueued Application actions have been completed.
        """
        write_output("applications_managed() issued, args:"
                     " %s" % (locals(),), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='aiai')
    def unsupported_applications(self, _manual_package_ids, _package_ids):
        """
        Notify Installed Applications that are no longer supported.
        "manual_package_ids" denotes the list of installed package ids
        that should be manually reviewed before removal, while
        "package_ids" denotes those safe to be removed.
        """
        write_output("unsupported_applications() issued, args:"
                     " %s" % (locals(),), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='a(sssaib)')
    def configuration_updates_available(self, _updates):
        """
        Notify the presence of configuration files that should be updated.
        The payload is a list of tuples, each one composed by:
        (root, source, destination, installed_package_ids, auto-mergeable)
        """
        write_output("configuration_updates_available() issued, args:"
                     " %s" % (locals(),), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='a(siss)')
    def preserved_libraries_available(self, _preserved):
        """
        Notify the presence of preserved libraries still on the system.
        The payload is a list of tuples, each one composed by:
        (library name, ELF class, library path, belonging atom)
        """
        write_output("preserved_libraries_available() issued, args:"
                     " %s" % (locals(),), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='asb')
    def repositories_settings_changed(self, _repository_ids, _success):
        """
        Notify that Repositories configuration has changed.
        This may include:
        - a repository has been enabled
        - a repository has been disabled
        - a repository has been renamed
        - a repository has been added
        - a repository has been removed
        """
        write_output("repositories_settings_changed() issued", debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='i')
    def restarting_system_upgrade(self, _updates_amount):
        """
        Notify that System Upgrade activity is being restarted because
        there are more updates available. This happens when the
        previous upgrade queue contained critical updates.
        """
        write_output("restarting_system_upgrade(): issued",
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='')
    def system_restart_needed(self):
        """
        Notify that a System restart is needed.
        """
        write_output("system_restart_needed(): issued",
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='i')
    def resources_unlock_request(self, activity):
        """
        Signal all the connected Clients to release their
        Entropy Resources Lock, if possible (both shared
        and exclusive). This is a kind request, it is
        not expected that clients actually acknowledge us.
        """
        write_output("resources_unlock_request() issued for %d" % (
                activity,), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='i')
    def resources_lock_request(self, activity):
        """
        Signal all the connected Clients to re-acquire shared
        Entropy Resources Lock. This is actually a mandatory
        request in order to run into really bad, inconsistent states.
        """
        write_output("resources_lock_request() issued for %d" % (
                activity,), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='i')
    def activity_started(self, activity):
        """
        Signal all the connected Clients that a scheduled activity
        has begun (and we're running with exclusive Entropy Resources
        access).
        """
        write_output("activity_started() issued for %d" % (
                activity,), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='ii')
    def activity_progress(self, activity, progress):
        """
        Signal all the connected Clients the ongoing activity
        progress state (from 0 to 100).
        """
        write_output("activity_progress() issued for %d, state: %i" % (
                activity, progress,), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='ib')
    def activity_completed(self, activity, success):
        """
        Signal all the connected Clients that a scheduled activity
        has been carried out.
        """
        write_output("activity_completed() issued for %d,"
                     " success: %s" % (
                activity, success,), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='iss')
    def application_enqueued(self, package_id, repository_id, action):
        """
        Signal all the connected Clients that a requested Application
        action has been accepted and the same enqueued.
        """
        write_output("application_enqueued(): %i,"
                     "%s, action: %s" % (
                package_id, repository_id, action,),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='isss')
    def processing_application(self, package_id, repository_id, action,
                               transaction_state):
        """
        Signal all the connected Clients that we're currently
        processing the given Application.
        """
        write_output("processing_application(): %i,"
                     "%s, action: %s, tx state: %s" % (
                package_id, repository_id, action,
                transaction_state,),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='issi')
    def application_processing_update(self, package_id, repository_id,
                                      app_transaction_state, progress):
        """
        Signal all the connected Clients an Application processing
        update.
        """
        write_output("application_processing_update(): %i,"
                     "%s, transaction_state: %s, progress: %i" % (
                package_id, repository_id,
                app_transaction_state,
                progress,),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='isss')
    def application_processed(self, package_id, repository_id,
                              action, app_outcome):
        """
        Signal all the connected Clients that we've completed
        the processing of given Application.
        """
        write_output("application_processed(): %d,"
                     "%s, action: %s, outcome: %s" % (
                package_id, repository_id, action, app_outcome,),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='a(sisssss)')
    def noticeboards_available(self, _notices):
        """
        Signal all the connected Clients that notice boards are
        available. It's up to the receiver to filter relevant
        information.
        """
        write_output("noticeboards_available(): %s" % (locals(),),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='a(is)asaiasb')
    def updates_available(self, _update, _update_atoms, _remove,
                          _remove_atoms, _one_click_updatable):
        """
        Signal all the connected Clients that there are updates
        available.
        """
        write_output("updates_available(): %s" % (locals(),),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='as')
    def unavailable_repositories(self, _repositories):
        """
        Signal all the connected Clients that there are updates
        unavailable repositories that would need to be downloaded.
        """
        write_output("unavailable_repositories(): %s" % (locals(),),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='')
    def old_repositories(self):
        """
        Signal all the connected Clients that available repositories
        are old and should be updated.
        """
        write_output("old_repositories(): %s" % (locals(),),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='asb')
    def mirrors_optimized(self, _repository_ids, _optimized):
        """
        Mirrors have been eventually optimized for given Repositories.
        """
        write_output("mirrors_optimized() issued, args:"
                     " %s" % (locals(),), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='')
    def ping(self):
        """
        Ping RigoDaemon dbus clients for answer.
        If no clients respond within 15 seconds,
        RigoDaemon will terminate.
        """
        write_output("ping() issued", debug=True)
        with self._ping_timer_mutex:
            if self._ping_timer is None:
                self._ping_timer = threading.Timer(15.0, self.stop)
                self._ping_timer.daemon = True
                self._ping_timer.start()

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='')
    def deferred_shutdown(self):
        """
        Signal that the deferred shutdown procedure has started.
        """
        write_output("deferred_shutdown(): %s" % (locals(),),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='')
    def shutdown(self):
        """
        Signal that RigoDaemon is shutting down in seconds.
        """
        write_output("shutdown(): %s" % (locals(),),
                     debug=True)

if __name__ == "__main__":
    if os.getuid() != 0:
        write_output("RigoDaemon: must run as root")
        raise SystemExit(1)
    try:
        daemon = RigoDaemonService()
    except dbus.exceptions.DBusException:
        raise SystemExit(1)
    main_loop = GLib.MainLoop()
    try:
        main_loop.run()
    except KeyboardInterrupt:
        raise SystemExit(1)
    raise SystemExit(0)
