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
from threading import Lock

# this makes the daemon to not write the entropy pid file
# avoiding to lock other instances
sys.argv.append('--no-pid-handling')

import dbus
import dbus.service
import dbus.mainloop.glib

from gi.repository import GLib, GObject

DAEMON_LOGGING = True
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
sys.path.insert(0, '/usr/lib/entropy/server')
sys.path.insert(0, '/usr/lib/entropy/client')
sys.path.insert(0, '../../lib')
sys.path.insert(0, '../../server')
sys.path.insert(0, '../../client')

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

TEXT = TextInterface()
DAEMON_LOGFILE = os.path.join(etpConst['syslogdir'], "rigo-daemon.log")
DAEMON_LOG = LogFile(SystemSettings()['system']['log_level']+1,
    DAEMON_LOGFILE, header = "[rigo-daemon]")
PREVIOUS_PROGRESS = ''

if DAEMON_LOGGING:
    # redirect possible exception tracebacks to log file
    sys.stderr = DAEMON_LOG
    sys.stdout = DAEMON_LOG

def write_output(*args, **kwargs):
    message = time.strftime('[%H:%M:%S %d/%m/%Y %Z]') + " " + args[0]
    global PREVIOUS_PROGRESS
    if PREVIOUS_PROGRESS == message:
        return
    PREVIOUS_PROGRESS = message
    if DAEMON_LOGGING:
        DAEMON_LOG.write(message)
        DAEMON_LOG.flush()
    if DAEMON_DEBUG:
        TEXT.output(*args, **kwargs)

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

    BUS_NAME = "org.sabayon.Rigo"
    OBJECT_PATH = "/daemon"

    """
    RigoDaemon is the dbus service Object in charge of executing
    privileged tasks, like repository updates, package installation
    and removal and so on.
    Mutual exclusion with other Entropy instances must be handled
    by the caller. Here it is assumed that Entropy Resources Lock
    is acquired in exclusive mode.
    """

    def __init__(self):
        object_path = RigoDaemonService.OBJECT_PATH
        dbus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default = True)
        system_bus = dbus.SystemBus(mainloop = dbus_loop)
        name = dbus.service.BusName(RigoDaemonService.BUS_NAME,
                                    bus = system_bus)
        dbus.service.Object.__init__(self, name, object_path)

        self._current_activity_mutex = Lock()
        self._current_activity = ActivityStates.AVAILABLE
        self._activity_mutex = Lock()
        Entropy.set_daemon(self)
        self._entropy = Entropy()
        write_output("__init__: dbus service loaded")

    def stop(self):
        """
        RigoDaemon exit method.
        """
        if DAEMON_DEBUG:
            write_output("stop(): called")
        with self._activity_mutex:
            with self._current_activity_mutex:
                self._current_activity = ActivityStates.NOT_AVAILABLE
            self._close_local_resources()
            if DAEMON_DEBUG:
                write_output("stop(): activity mutex acquired, quitting")
            entropy.tools.kill_threads()
            os.kill(os.getpid(), signal.SIGTERM)

    def _update_repositories(self, repositories, request_id, force):
        """
        Repositories Update execution code.
        """
        with self._activity_mutex:
            with self._current_activity_mutex:
                self._current_activity = ActivityStates.UPDATING_REPOSITORIES
            self._close_local_resources()
            result = 99
            try:
                updater = self._entropy.Repositories(
                    repositories, force = force)
                result = updater.unlocked_sync()
            except AttributeError as err:
                write_output("_update_repositories error: %s" % (err,))
                self.repositories_updated(
                    request_id, 1,
                    _("No repositories configured"))
                return
            except Exception as err:
                write_output("_update_repositories error 2: %s" % (err,))
                self.repositories_updated(
                    request_id, 2,
                    _("Unhandled Exception"))
                return
            finally:
                with self._current_activity_mutex:
                    self._current_activity = \
                        ActivityStates.AVAILABLE
                self.repositories_updated(request_id, result, "")

    def _close_local_resources(self):
        """
        Close any Entropy resource that might have been changed
        or replaced.
        """
        self._entropy.reopen_installed_repository()
        self._entropy.close_repositories()

    ### DBUS METHODS

    @dbus.service.method(BUS_NAME, in_signature='asib',
        out_signature='')
    def update_repositories(self, repositories, request_id, force):
        """
        Request RigoDaemon to update the given repositories.
        At the end of the execution, the "repositories_updated"
        signal will be raised.
        """
        if DAEMON_DEBUG:
            write_output("update_repositories called: %s, id: %i" % (
                    repositories, request_id,))
        task = ParallelTask(self._update_repositories, repositories,
                            request_id, force)
        task.daemon = True
        task.name = "UpdateRepositoriesThread"
        task.start()

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def connect(self):
        """
        Notify us that a new client is now connected.
        Here we reload Entropy configuration and other resources.
        """
        if DAEMON_DEBUG:
            write_output("connect(): called")
        with self._activity_mutex:
            initconfig_entropy_constants(etpConst['systemroot'])
            self._entropy.Settings().clear()
            self._entropy._validate_repositories()
            self._close_local_resources()
            if DAEMON_DEBUG:
                write_output("A new client is now connected !")

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='i')
    def activity(self):
        """
        Return RigoDaemon activity states (any of RigoDaemon.ActivityStates
        values).
        """
        with self._current_activity_mutex:
            return self._current_activity

    @dbus.service.method(BUS_NAME, in_signature='',
        out_signature='')
    def output_test(self):
        """
        Return whether RigoDaemon is busy due to previous activity.
        """
        def _deptester():
            with self._activity_mutex:
                with self._current_activity_mutex:
                    self._current_activity = \
                        ActivityStates.INTERNAL_ROUTINES

                self._entropy.dependencies_test()

                with self._current_activity_mutex:
                    self._current_activity = \
                        ActivityStates.AVAILABLE

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
        signature='iis')
    def repositories_updated(self, request_id, result, message):
        """
        Repositories have been updated. This signal comes from
        the request_id passed to update_repositories().
        "result" is an integer carrying execution return status.
        """
        if DAEMON_DEBUG:
            write_output("repositories_updated() issued, args:"
                         " %s" % (locals(),))


if __name__ == "__main__":
    try:
        daemon = RigoDaemonService()
    except dbus.exceptions.DBusException:
        raise SystemExit(1)
    GLib.threads_init()
    main_loop = GObject.MainLoop()
    main_loop.run()
    raise SystemExit(0)
