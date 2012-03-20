#!/usr/bin/python2 -O
# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-3

    B{Entropy Package Manager Rigo Daemon}.

"""
import os
import sys
import time
import signal
from threading import Lock, Timer, Semaphore
from collections import deque

# this makes the daemon to not write the entropy pid file
# avoiding to lock other instances
sys.argv.append('--no-pid-handling')

import dbus
import dbus.service
import dbus.mainloop.glib

from gi.repository import GLib, GObject

DAEMON_LOGGING = False
DAEMON_DEBUG = False
# If place here, we won't trigger etpUi['debug']
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

from entropy.const import etpConst, const_convert_to_rawstring, \
    initconfig_entropy_constants, const_debug_write
from entropy.i18n import _
from entropy.misc import LogFile, ParallelTask, TimeScheduled
from entropy.fetchers import UrlFetcher
from entropy.output import TextInterface
from entropy.client.interfaces import Client
from entropy.core.settings.base import SystemSettings

import entropy.tools

from RigoDaemon.enums import ActivityStates
from RigoDaemon.config import DbusConfig

TEXT = TextInterface()
DAEMON_LOGFILE = os.path.join(etpConst['syslogdir'], "rigo-daemon.log")
DAEMON_LOG = LogFile(SystemSettings()['system']['log_level']+1,
    DAEMON_LOGFILE, header = "[rigo-daemon]")

if DAEMON_LOGGING:
    # redirect possible exception tracebacks to log file
    sys.stderr = DAEMON_LOG
    sys.stdout = DAEMON_LOG

def write_output(message, debug=False):
    message = time.strftime('[%H:%M:%S %d/%m/%Y %Z]') + " " + message
    if DAEMON_LOGGING:
        DAEMON_LOG.write(message)
        DAEMON_LOG.flush()
    if DAEMON_DEBUG:
        if debug:
            const_debug_write(__name__, message, force=True)
        else:
            TEXT.output(message)

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def handle_exception(exc_class, exc_instance, exc_tb):
    t_back = entropy.tools.get_traceback(tb_obj = exc_tb)
    # restore original exception handler, to avoid loops
    uninstall_exception_handler()
    # write exception to log file
    write_output(const_convert_to_rawstring(t_back), debug=True)
    raise exc_instance

install_exception_handler()

class Entropy(Client):

    _DAEMON = None

    def init_singleton(self):
        Client.init_singleton(self, load_ugc=False,
            url_fetcher=DaemonUrlFetcher, repo_validation=False)
        write_output(
            "Loading Entropy Rigo daemon: logfile: %s" % (
                DAEMON_LOGFILE,)
            )

    @staticmethod
    def set_daemon(daemon):
        """
        Bind the Entropy Singleton instance to the DBUS Daemon.
        """
        Entropy._DAEMON = daemon
        DaemonUrlFetcher.set_daemon(daemon)

    def output(self, text, header = "", footer = "", back = False,
        importance = 0, level = "info", count = None, percent = False):
        if self._DAEMON is not None:
            count_c = 0
            count_t = 0
            if count is not None:
                count_c, count_t = count
            self._DAEMON.output(
                text, header, footer, back, importance,
                level, count_c, count_t, percent)

Client.__singleton_class__ = Entropy

class DaemonUrlFetcher(UrlFetcher):

    daemon_last_avg = 100
    __average = 0
    __downloadedsize = 0
    __remotesize = 0
    __datatransfer = 0
    __time_remaining = ""

    _DAEMON = None

    @staticmethod
    def set_daemon(daemon):
        """
        Bind RigoDaemon instance to this class.
        """
        DaemonUrlFetcher._DAEMON = daemon

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

        self._DAEMON.transfer_output(
            self.__average, self.__downloadedsize,
            int(self.__remotesize), int(self.__datatransfer),
            self.__time_remaining)


class RigoDaemonService(dbus.service.Object):

    BUS_NAME = DbusConfig.BUS_NAME
    OBJECT_PATH = DbusConfig.OBJECT_PATH

    """
    RigoDaemon is the dbus service Object in charge of executing
    privileged tasks, like repository updates, package installation
    and removal and so on.
    Mutual exclusion with other Entropy instances must be handled
    by the caller. Here it is assumed that Entropy Resources Lock
    is acquired in exclusive mode.
    """

    class ActionQueueItem(object):

        def __init__(self, package_id, repository_id, action):
            self._package_id = package_id
            self._repository_id = repository_id
            self._action = action

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

        def action(self):
            """
            Return AppActions Action for this ActionQueueItem.
            """
            return self._action

        def __str__(self):
            """
            Show item in human readable way
            """
            return "ActionQueueItem{%s, %s}" % (
                self.pkg, self.action())

        def __repr__(self):
            """
            Same as __str__
            """
            return str(self)


    def __init__(self):
        object_path = RigoDaemonService.OBJECT_PATH
        dbus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default = True)
        system_bus = dbus.SystemBus(mainloop = dbus_loop)
        name = dbus.service.BusName(RigoDaemonService.BUS_NAME,
                                    bus = system_bus)
        dbus.service.Object.__init__(self, name, object_path)

        # used by non-daemon thread to exit
        self._stop_signal = False

        # used to determine if there are connected clients
        self._ping_timer_mutex = Lock()
        self._ping_timer = None

        self._current_activity_mutex = Lock()
        self._current_activity = ActivityStates.AVAILABLE
        self._activity_mutex = Lock()

        self._acquired_exclusive = False
        self._acquired_exclusive_mutex = Lock()

        self._action_queue = deque()
        self._action_queue_waiter = Semaphore(0)
        self._enqueue_action_busy_hold_mutex = Lock()
        self._action_queue_task = ParallelTask(
            self._action_queue_worker_thread)
        self._action_queue_task.name = "ActionQueueWorkerThread"
        self._action_queue_task.daemon = True
        # do not daemonize !!
        self._action_queue_task.start()

        Entropy.set_daemon(self)
        self._entropy = Entropy()
        write_output(
            "__init__: dbus service loaded, pid: %d, ppid: %d" %  (
                os.getpid(), os.getppid(),)
                )

        def _sigusr2_activate_shutdown(signum, frame):
            write_output("SIGUSR2: activating shutdown...", debug=True)
            # ask clients to pong
            task = TimeScheduled(30.0, self.ping)
            task.set_delay_before(False)
            task.name = "ShutdownPinger"
            task.daemon = True
            task.start()

        signal.signal(signal.SIGUSR2, _sigusr2_activate_shutdown)

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
                raise ActivityStates.AlreadyAvailabileError()
            self._current_activity = ActivityStates.AVAILABLE

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
            # use kill so that GObject main loop will quit as well
            os.kill(os.getpid(), signal.SIGTERM)

    def _update_repositories(self, repositories, force, activity):
        """
        Repositories Update execution code.
        """
        with self._activity_mutex:

            # ask clients to release their locks
            self._acquire_exclusive(activity)
            result = 99
            msg = ""
            try:
                self._close_local_resources()
                self._entropy_setup()
                self.activity_started(activity)

                if not repositories:
                    repositories = list(
                        SystemSettings()['repositories']['available'])
                write_output("_update_repositories(): %s" % (
                        repositories,), debug=True)

                updater = self._entropy.Repositories(
                    repositories, force = force)
                result = updater.unlocked_sync()

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
                try:
                    self._unbusy(activity)
                except ActivityStates.AlreadyAvailableError:
                    write_output("_update_repositories._unbusy: already "
                                 "available, wtf !?!?")
                    # wtf??
                self._release_exclusive(activity)
                self.activity_completed(activity, result == 0)
                self.repositories_updated(result, msg)

    def _action_queue_worker_thread(self):
        """
        Worker thread that handles Application Action requests
        from Rigo Clients.
        """
        activity = ActivityStates.MANAGING_APPLICATIONS

        def _action_queue_finally():
            with self._enqueue_action_busy_hold_mutex:
                # unbusy?
                has_more = self._action_queue_waiter.acquire(False)
                if has_more:
                    # put it back
                    self._action_queue_waiter.release()
                else:
                    try:
                        self._unbusy(activity)
                    except ActivityStates.AlreadyAvailableError:
                        write_output("_action_queue_worker_thread"
                                     "._unbusy: already "
                                     "available, wtf !?!?")
                        # wtf??
                    self._release_exclusive(activity)
                    self.activity_completed(activity, True)
                    self.applications_managed(True)

        while True:

            self._action_queue_waiter.acquire() # CANBLOCK
            if self._stop_signal:
                write_output("_action_queue_worker_thread: bye bye!",
                             debug=True)
                # bye bye!
                break

            try:
                item = self._action_queue.popleft()
            except IndexError:
                # mumble, no more items, this shouldn't have happened
                write_output("_action_queue_worker_thread: "
                             "no item popped!", debug=True)
                continue

            write_output("_action_queue_worker_thread: "
                         "got: %s" % (item,), debug=True)

            # now execute the action
            with self._activity_mutex:

                self._acquire_exclusive(activity)
                try:
                    self._close_local_resources()
                    self._entropy_setup()
                    self.activity_started(activity)

                    write_output("_action_queue_worker_thread: "
                                 "doing %s" % (
                            item,), debug=True)
                    self._process_action(item)

                finally:
                    _action_queue_finally()

    def _process_action(self, item):
        """
        This is the real Application Action processing function.
        """
        package_id, repository_id = item.pkg
        action = item.action()

        self.processing_application(package_id, repository_id, action)
        success = False
        try:
            # FIXME, complete
            # 1. calculate dependencies
            # 2. notify (and block) if conflicts arise
            # 3. ?? TBD show install/removal queue?
            # 4. [GUI?] if removal, ask if action is really wanted?
            # 5. [GUI?] if system package, avoid removal?
            # simulate
            self._entropy.output("Application Management Message")
            time.sleep(35)
            self._entropy.output("Application Management Complete")
            success = True
        finally:
            self.application_processed(
                package_id, repository_id, action, success)

    def _close_local_resources(self):
        """
        Close any Entropy resource that might have been changed
        or replaced.
        """
        self._entropy.reopen_installed_repository()
        self._entropy.close_repositories()

    def _acquire_exclusive(self, activity):
        """
        Acquire Exclusive access to Entropy Resources.
        Note: this is blocking and will issue the
        exclusive_acquired() signal when done.
        """
        acquire = False
        with self._acquired_exclusive_mutex:
            if not self._acquired_exclusive:
                # now we got the exclusive lock
                self._acquired_exclusive = True
                acquire = True

        if acquire:
            write_output("_acquire_exclusive: about to acquire lock",
                         debug=True)
            acquired = self._entropy.lock_resources(
                blocking=False,
                shared=False)
            if not acquired:
                write_output("_acquire_exclusive: asking to unlock",
                             debug=True)
                self.resources_unlock_request(activity)
                self._entropy.lock_resources(
                    blocking=True,
                    shared=False)

            write_output("_acquire_exclusive: just acquired lock",
                         debug=True)

    def _release_exclusive(self, activity):
        """
        Release Exclusive access to Entropy Resources.
        """
        # make sure to not release locks as long
        # as there is activity
        with self._acquired_exclusive_mutex:
            if self._acquired_exclusive:
                self.resources_lock_request(activity)
                self._entropy.unlock_resources()
                # now we got the exclusive lock
                self._acquired_exclusive = False

    def _entropy_setup(self):
        """
        Notify us that a new client is now connected.
        Here we reload Entropy configuration and other resources.
        """
        write_output("_entropy_setup(): called", debug=True)

        initconfig_entropy_constants(etpConst['systemroot'])
        self._entropy.Settings().clear()
        self._entropy._validate_repositories()
        self._close_local_resources()
        write_output("_entropy_setup(): complete", debug=True)

    ### DBUS METHODS

    @dbus.service.method(BUS_NAME, in_signature='asb',
        out_signature='b')
    def update_repositories(self, repositories, force):
        """
        Request RigoDaemon to update the given repositories.
        At the end of the execution, the "repositories_updated"
        signal will be raised.
        """
        write_output("update_repositories called: %s" % (
                repositories,), debug=True)

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
                            force, activity)
        task.daemon = True
        task.name = "UpdateRepositoriesThread"
        task.start()
        return True

    @dbus.service.method(BUS_NAME, in_signature='iss',
        out_signature='b')
    def enqueue_application_action(self, package_id, repository_id,
                                   action):
        """
        Request RigoDaemon to enqueue a new Application Action, if
        possible.
        """
        write_output("enqueue_application_action called: %s, %s" % (
                (package_id, repository_id), action,), debug=True)

        with self._enqueue_action_busy_hold_mutex:

            activity = ActivityStates.MANAGING_APPLICATIONS
            try:
                self._busy(activity)
            except ActivityStates.BusyError:
                # I am already busy doing other stuff, cannot
                # satisfy request
                return False
            except ActivityStates.SameError:
                # I am already busy doing this, so just enqueue
                write_output("enqueue_application_action: "
                             "already busy, just enqueue",
                             debug=True)

            item = self.ActionQueueItem(
                package_id,
                repository_id,
                action)
            self._action_queue.append(item)
            self._action_queue_waiter.release()
            return True

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
        out_signature='b')
    def exclusive(self):
        """
        Return whether RigoDaemon is running in with
        Entropy Resources acquired in exclusive mode.
        """
        write_output("is_exclusive called: %s, %s", debug=True)

        return self._acquired_exclusive

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

    ### DBUS SIGNALS

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='sssbisiib')
    def output(self, text, header, footer, back, importance, level,
               count_c, count_t, percent):
        """
        Entropy Library output text signal. Clients will be required to
        forward this message to User.
        """
        pass

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='iiiis')
    def transfer_output(self, average, downloaded_size,
                        total_size, data_transfer_bytes,
                        time_remaining_secs):
        """
        Entropy UrlFetchers output signals. Clients will be required to
        forward this message to User in Progress Bar form.
        """
        pass

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='is')
    def repositories_updated(self, result, message):
        """
        Repositories have been updated.
        "result" is an integer carrying execution return status.
        """
        write_output("repositories_updated() issued, args:"
                     " %s" % (locals(),), debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='b')
    def applications_managed(self, success):
        """
        Enqueued Application actions have been completed.
        """
        write_output("applications_managed() issued, args:"
                     " %s" % (locals(),), debug=True)

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
    def processing_application(self, package_id, repository_id, action):
        """
        Signal all the connected Clients that we're currently
        processing the given Application.
        """
        write_output("processing_application(): %d,"
                     "%s, action: %s" % (
                package_id, repository_id, action,),
                     debug=True)

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='issb')
    def application_processed(self, package_id, repository_id,
                              action, success):
        """
        Signal all the connected Clients that we've completed
        the processing of given Application.
        """
        write_output("application_processed(): %d,"
                     "%s, action: %s, success: %s" % (
                package_id, repository_id, action, success,),
                     debug=True)


    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='')
    def ping(self):
        """
        Ping RigoDaemon dbus clients for answer.
        If no clients respond within 15 seconds,
        RigoDaemon will terminate.
        This signal is spawned after having
        received SIGUSR2.
        """
        write_output("ping() issued", debug=True)
        with self._ping_timer_mutex:
            if self._ping_timer is None:
                self._ping_timer = Timer(15.0, self.stop)
                self._ping_timer.start()

if __name__ == "__main__":
    if os.getuid() != 0:
        write_output("RigoDaemon: must run as root")
        raise SystemExit(1)
    try:
        daemon = RigoDaemonService()
    except dbus.exceptions.DBusException:
        raise SystemExit(1)
    GLib.threads_init()
    main_loop = GObject.MainLoop()
    try:
        main_loop.run()
    except KeyboardInterrupt:
        raise SystemExit(1)
    raise SystemExit(0)
