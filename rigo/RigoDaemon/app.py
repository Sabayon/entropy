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
from threading import Lock, Timer

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
    initconfig_entropy_constants
from entropy.i18n import _
from entropy.misc import LogFile, ParallelTask, TimeScheduled
from entropy.fetchers import UrlFetcher
from entropy.output import TextInterface, darkred, darkgreen, red
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

def write_output(*args, **kwargs):
    message = time.strftime('[%H:%M:%S %d/%m/%Y %Z]') + " " + args[0]
    if DAEMON_LOGGING:
        DAEMON_LOG.write(message)
        DAEMON_LOG.flush()
    if DAEMON_DEBUG:
        TEXT.output(message, *args[1:], **kwargs)

def install_exception_handler():
    sys.excepthook = handle_exception

def uninstall_exception_handler():
    sys.excepthook = sys.__excepthook__

def handle_exception(exc_class, exc_instance, exc_tb):
    t_back = entropy.tools.get_traceback(tb_obj = exc_tb)
    # restore original exception handler, to avoid loops
    uninstall_exception_handler()
    # write exception to log file
    write_output(const_convert_to_rawstring(t_back))
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

        mytxt = _("[F]")
        eta_txt = _("ETA")
        sec_txt = _("sec") # as in XX kb/sec

        current_txt = darkred("    %s: " % (mytxt,)) + \
            darkgreen(str(round(float(self.__downloadedsize)/1024, 1))) + "/" \
            + red(str(round(self.__remotesize, 1))) + " kB"
        # create progress bar
        barsize = 10
        bartext = "["
        curbarsize = 1

        averagesize = (self.__average*barsize)/100
        while averagesize > 0:
            curbarsize += 1
            bartext += "="
            averagesize -= 1
        bartext += ">"
        diffbarsize = barsize - curbarsize
        while diffbarsize > 0:
            bartext += " "
            diffbarsize -= 1
        bartext += "] => %s" % (
            entropy.tools.bytes_into_human(self.__datatransfer),)
        bartext += "/%s : %s: %s" % (sec_txt, eta_txt,
                                     self.__time_remaining,)
        average = str(self.__average)
        if len(average) < 2:
            average = " "+average
        current_txt += " <->  "+average+"% "+bartext

        self._DAEMON.output(
            current_txt, "", "", True, 0,
            "info", 0, 0, False)

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

    class BusyError(Exception):
        """
        Cannot acknowledge a Local Activity change.
        """

    class AlreadyAvailableError(Exception):
        """
        Cannot acknowledge a Local Activity change to
        "AVAILABLE" state, because we're already ready.
        """

    class UnbusyFromDifferentActivity(Exception):
        """
        Unbusy request from different activity.
        """

    def __init__(self):
        object_path = RigoDaemonService.OBJECT_PATH
        dbus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default = True)
        system_bus = dbus.SystemBus(mainloop = dbus_loop)
        name = dbus.service.BusName(RigoDaemonService.BUS_NAME,
                                    bus = system_bus)
        dbus.service.Object.__init__(self, name, object_path)

        self._ping_timer_mutex = Lock()
        self._ping_timer = None
        self._ping_sched = TimeScheduled(3, self.ping)
        self._ping_sched.set_delay_before(True)
        self._ping_sched.daemon = True
        self._ping_sched.name = "PingThread"
        self._ping_sched_startup = Lock()

        self._current_activity_mutex = Lock()
        self._current_activity = ActivityStates.AVAILABLE
        self._activity_mutex = Lock()

        self._acquired_exclusive = False
        self._acquired_exclusive_mutex = Lock()

        Entropy.set_daemon(self)
        self._entropy = Entropy()
        write_output(
            "__init__: dbus service loaded, pid: %d, ppid: %d" %  (
                os.getpid(), os.getppid(),)
                )

    def _busy(self, activity):
        """
        Switch to busy activity state, if possible.
        Raise RigoDaemonService.BusyError if already busy.
        """
        with self._current_activity_mutex:
            if self._current_activity != ActivityStates.AVAILABLE:
                raise RigoDaemonService.BusyError()
            self._current_activity = activity

    def _unbusy(self, activity, _force=False):
        """
        Unbusy from previous Activity.
        Raise RigoDaemonService.AlreadyAvailableError if already
        AVAILABLE.
        Raise RigoDaemonService.UnbusyFromDifferentActivity if
        provided activity differs from the current one.
        """
        with self._current_activity_mutex:
            if activity != self._current_activity and not _force:
                raise RigoDaemonService.UnbusyFromDifferentActivity()
            if activity == ActivityStates.AVAILABLE and not _force:
                raise RigoDaemonService.AlreadyAvalabileError()
            self._current_activity = ActivityStates.AVAILABLE

    def stop(self):
        """
        RigoDaemon exit method.
        """
        if DAEMON_DEBUG:
            write_output("stop(): called")
        with self._activity_mutex:
            self._ping_sched.kill()
            try:
                self._busy(ActivityStates.NOT_AVAILABLE, _force=True)
            except RigoDaemonService.AlreadyAvailableError:
                pass
            self._close_local_resources()
            if DAEMON_DEBUG:
                write_output("stop(): activity mutex acquired, quitting")
            entropy.tools.kill_threads()
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
                if DAEMON_DEBUG:
                    write_output("_update_repositories(): %s" % (
                            repositories,))

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
                except RigoDaemonService.AlreadyAvailableError:
                    write_output("_update_repositories._unbusy: already "
                                 "available, wtf !?!?")
                    # wtf??
                self._release_exclusive(activity)
                self.activity_completed(activity, result == 0)
                self.repositories_updated(result, msg)

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
            if DAEMON_DEBUG:
                write_output("_acquire_exclusive: about to acquire lock")
            acquired = self._entropy.lock_resources(
                blocking=False,
                shared=False)
            if not acquired:
                if DAEMON_DEBUG:
                    write_output("_acquire_exclusive: asking to unlock")
                self.resources_unlock_request(activity)
                self._entropy.lock_resources(
                    blocking=True,
                    shared=False)
            if DAEMON_DEBUG:
                write_output("_acquire_exclusive: just acquired lock")

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
        if DAEMON_DEBUG:
            write_output("_entropy_setup(): called")
        acquired = self._ping_sched_startup.acquire(False)
        if acquired:
            if DAEMON_DEBUG:
                write_output("_entropy_setup(): starting ping() signaling")
            self._ping_sched.start()

        initconfig_entropy_constants(etpConst['systemroot'])
        self._entropy.Settings().clear()
        self._entropy._validate_repositories()
        self._close_local_resources()
        if DAEMON_DEBUG:
            write_output("_entropy_setup(): complete")

    ### DBUS METHODS

    @dbus.service.method(BUS_NAME, in_signature='asb',
        out_signature='b')
    def update_repositories(self, repositories, force):
        """
        Request RigoDaemon to update the given repositories.
        At the end of the execution, the "repositories_updated"
        signal will be raised.
        """
        activity = ActivityStates.UPDATING_REPOSITORIES
        try:
            self._busy(activity)
        except RigoDaemonService.BusyError:
            # I am already busy doing other stuff, cannot
            # satisfy request
            return False

        if DAEMON_DEBUG:
            write_output("update_repositories called: %s" % (
                    repositories,))
        task = ParallelTask(self._update_repositories, repositories,
                            force, activity)
        task.daemon = True
        task.name = "UpdateRepositoriesThread"
        task.start()
        return True

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='i')
    def activity(self):
        """
        Return RigoDaemon activity states (any of RigoDaemon.ActivityStates
        values).
        """
        return self._current_activity

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='b')
    def is_exclusive(self):
        """
        Return whether RigoDaemon is running in with
        Entropy Resources acquired in exclusive mode.
        """
        return self._acquired_exclusive

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def pong(self):
        """
        Answer to RigoDaemon ping() events.
        """
        if DAEMON_DEBUG:
            write_output("pong() received")
        with self._ping_timer_mutex:
            if self._ping_timer is not None:
                # stop the bomb!
                self._ping_timer.cancel()
                self._ping_timer = None

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def output_test(self):
        """
        Return whether RigoDaemon is busy due to previous activity.
        """
        def _deptester():
            with self._activity_mutex:
                self._entropy.dependencies_test()

        task = ParallelTask(_deptester)
        task.daemon = True
        task.name = "OutputTestThread"
        task.start()

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
        if DAEMON_DEBUG:
            write_output("repositories_updated() issued, args:"
                         " %s" % (locals(),))

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='i')
    def resources_unlock_request(self, activity):
        """
        Signal all the connected Clients to release their
        Entropy Resources Lock, if possible (both shared
        and exclusive). This is a kind request, it is
        not expected that clients actually acknowledge us.
        """
        if DAEMON_DEBUG:
            write_output("resources_unlock_request() issued for %d" % (
                    activity,))

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='i')
    def resources_lock_request(self, activity):
        """
        Signal all the connected Clients to re-acquire shared
        Entropy Resources Lock. This is actually a mandatory
        request in order to run into really bad, inconsistent states.
        """
        if DAEMON_DEBUG:
            write_output("resources_lock_request() issued for %d" % (
                    activity,))

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='i')
    def activity_started(self, activity):
        """
        Signal all the connected Clients that a scheduled activity
        has begun (and we're running with exclusive Entropy Resources
        access).
        """
        if DAEMON_DEBUG:
            write_output("activity_started() issued for %d" % (
                    activity,))

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='ib')
    def activity_completed(self, activity, success):
        """
        Signal all the connected Clients that a scheduled activity
        has been carried out.
        """
        if DAEMON_DEBUG:
            write_output("activity_completed() issued for %d,"
                         " success: %s" % (
                    activity, success,))

    @dbus.service.signal(dbus_interface=BUS_NAME,
        signature='')
    def ping(self):
        """
        Ping RigoDaemon dbus clients for answer.
        If no clients respond within 15 seconds,
        Entropy Resources will be released completely.
        """
        def _time_up():
            if DAEMON_DEBUG:
                write_output("time is up! issuing _release_exclusive()")
            self._unbusy(None, _force=True)
            with self._activity_mutex:
                self._release_exclusive()
            if DAEMON_DEBUG:
                write_output("issued _release_exclusive()")

        if DAEMON_DEBUG:
            write_output("ping() issued")
        with self._ping_timer_mutex:
            if self._ping_timer is None and self._acquired_exclusive:
                self._ping_timer = Timer(15.0, _time_up)
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
