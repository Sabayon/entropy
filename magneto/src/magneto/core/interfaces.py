# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) core interfaces}

"""

# System imports
import os
import sys
import time
import subprocess
import dbus
import dbus.exceptions
from threading import Lock

# Entropy imports
from entropy.output import nocolor
from entropy.client.interfaces import Client
from entropy.const import etpConst, const_debug_write
import entropy.tools
from entropy.i18n import _, ngettext
from entropy.misc import ParallelTask

# Magneto imports
from magneto.core import config

# RigoDaemon imports
from RigoDaemon.config import DbusConfig
from RigoDaemon.enums import ActivityStates

class MagnetoCoreUI:

    """
    Methods in this class are inherited by MagnetoCore and should be
    reimplemented by its subclasses.
    """

    def set_unlock_callback(self, unlock_callback):
        """
        Set the Magneto execution Lock unlock callback.
        """
        self._unlock_callback = unlock_callback

    def startup(self):
        """
        Graphical Interface startup method.
        Must be reimplemented.
        """
        raise NotImplementedError()

    def show_alert(self, title, text, urgency = None, force = False):
        """
        This method is used for calling the popup notification widget.

        @param title: alert title
        @type title: string
        @param text: alert message
        @type text: string
        @param urgency: urgency identifier (can be "critical" or "low")
        @type urgency: string
        @param force: force user notification
        @type force: bool
        """
        raise NotImplementedError()

    def update_tooltip(self, tip):
        """
        Update applet tooltip

        @param tip: new tooltip text
        @type tip: string
        """
        raise NotImplementedError()

    def change_icon(self, image):
        """
        Update applet icon
        """
        raise NotImplementedError()

    def applet_context_menu(self):
        """
        When context menu action is triggered
        """
        raise NotImplementedError()

    def show_notice_window(self):
        """
        Show the Updates Notification window
        """
        raise NotImplementedError()

    def hide_notice_window(self):
        """
        Hide the Updates Notification window
        """
        raise NotImplementedError()


class MagnetoCore(MagnetoCoreUI):
    """
    Magneto base UI interface, must be subclassed to make it support Qt/GTK
    interfaces.
    """

    _UPDATES_AVAILABLE_SIGNAL = "updates_available"
    _ACTIVITY_STARTED_SIGNAL = "activity_started"
    _REPOSITORIES_UPDATED_SIGNAL = "repositories_updated"
    _SHUTDOWN_SIGNAL = "shutdown"

    DBUS_INTERFACE = DbusConfig.BUS_NAME
    DBUS_PATH = DbusConfig.OBJECT_PATH

    def __init__(self, icon_loader_class, main_loop_class):

        if "--debug" not in sys.argv:
            import signal
            signal.signal(signal.SIGINT, signal.SIG_DFL)

        self._unlock_callback = None
        self.__dbus_main_loop = None
        self.__system_bus = None
        self.__entropy_bus = None
        self.__entropy_bus_mutex = Lock()

        # Set this to True when DBus service is up
        self._dbus_service_available = False
        # Notice Window Widget status
        self.notice_window_shown = None
        # List of package updates available
        self.package_updates = []
        # Last alert message
        self.last_alert = None
        # Last time updates check has been issued
        self.last_trigger_check_t = 0.0
        # Applet current state
        self.current_state = None
        # Applet manual check selected
        self.manual_check_triggered = False

        self.icons = icon_loader_class()
        self.icons.add_file("okay", "applet-okay.png")
        self.icons.add_file("error", "applet-error.png")
        self.icons.add_file("busy", "applet-busy.png")
        self.icons.add_file("critical", "applet-critical.png")
        self.icons.add_file("disable", "applet-disable.png")
        self.icons.add_file("pm", "pm.png")
        self.icons.add_file("web", "applet-web.png")
        self.icons.add_file("configuration", "applet-configuration.png")
        self.applet_size = 22

        # Dbus variables
        self._dbus_init_error_msg = 'Unknown error'

        self._menu_item_list = (
            ("disable_applet", _("_Disable Notification Applet"),
                _("Disable Notification Applet"), self.disable_applet),
            ("enable_applet", _("_Enable Notification Applet"),
                _("Enable Notification Applet"), self.enable_applet),
            ("check_now", _("_Check for updates"),
                _("Check for updates"), self.send_check_updates_signal),
            ("update_now", _("_Launch Package Manager"),
                _("Launch Package Manager"), self.launch_package_manager),
            ("web_panel", _("_Packages Website"),
                _("Use Packages web interface"), self.load_packages_url),
            ("web_site", _("_Sabayon Linux Website"),
                _("Launch Sabayon Linux Website"), self.load_website),
            None,
            ("application-exit", _("_Exit"), _("Exit"), self.exit_applet),
        )

        self._main_loop_class = main_loop_class

    @property
    def _dbus_main_loop(self):
        if self.__dbus_main_loop is None:
            self.__dbus_main_loop = self._main_loop_class(
                set_as_default=True)
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

                const_debug_write(
                    __name__,
                    "_entropy_bus: loading RigoDaemon DBus Object")

                # RigoDaemon is telling us that a new activity
                # has just begun
                self.__entropy_bus.connect_to_signal(
                    self._ACTIVITY_STARTED_SIGNAL,
                    self._activity_started_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                # RigoDaemon tells us that there are app updates
                # available
                self.__entropy_bus.connect_to_signal(
                    self._UPDATES_AVAILABLE_SIGNAL,
                    self._updates_available_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                self.__entropy_bus.connect_to_signal(
                    self._REPOSITORIES_UPDATED_SIGNAL,
                    self._repositories_updated_signal,
                    dbus_interface=self.DBUS_INTERFACE)

                self.__entropy_bus.connect_to_signal(
                    self._SHUTDOWN_SIGNAL,
                    self._shutdown_signal,
                    dbus_interface=self.DBUS_INTERFACE)

            return self.__entropy_bus

    def setup_dbus(self):
        """
        Dbus Setup method.
        """
        try:
            self._entropy_bus
            self._dbus_service_available = True
            return True
        except dbus.exceptions.DBusException as err:
            self._dbus_service_available = False
            self._dbus_init_error_msg = "%s" % (err,)
            return False

    def _shutdown_signal(self):
        """
        Discard RigoDaemon bus object if shutdown() arrived.
        """
        self.__entropy_bus_mutex.acquire()
        const_debug_write(
            __name__,
            "shutdown() arrived, reloading in 2 seconds")
        time.sleep(2)
        if self._unlock_callback is not None:
            self._unlock_callback()
        os.execvp("magneto", sys.argv)

    def _activity_started_signal(self, activity):
        """
        RigoDaemon is telling us that the scheduled activity,
        either by us or by another Rigo, has just begun and
        that it, RigoDaemon, has now exclusive access to
        Entropy Resources.
        """
        if activity == ActivityStates.UPDATING_REPOSITORIES:
            self.updating_signal()

    def _repositories_updated_signal(self, result, message):
        """
        Repositories have been updated, ask for info
        """
        self._hello()

    def _hello(self):
        """
        Say hello to RigoDaemon. This causes the sending of
        several welcome signals, such as updates notification.
        """
        return dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).hello()

    def _update_repositories(self):
        """
        Spawn Repositories Update on RigoDaemon.
        """
        accepted = dbus.Interface(
            self._entropy_bus,
            dbus_interface=self.DBUS_INTERFACE).update_repositories(
            [], False)
        return accepted

    def _dbus_to_unicode(self, dbus_string):
        """
        Convert dbus.String() to unicode object
        """
        return dbus_string.decode(etpConst['conf_encoding'])

    def _updates_available_signal(self, update, update_atoms,
                                  remove, remove_atoms):
        updates = [self._dbus_to_unicode(x) for x in update_atoms]
        self.new_updates_signal(updates)

    def show_service_not_available(self):
        # inform user about missing Entropy service
        self.show_alert(
            _("Cannot monitor Sabayon updates"),
            "%s: %s: %s" % (
                _("Entropy DBus service not available"),
                _("unable to communicate with the updates service"),
                self._dbus_init_error_msg,
            ),
            urgency = "critical"
        )

    def new_updates_signal(self, update_atoms):
        if not config.settings['APPLET_ENABLED']:
            return

        del self.package_updates[:]
        self.package_updates.extend(update_atoms)
        upd_len = len(update_atoms)

        if upd_len:
            self.update_tooltip(ngettext("There is %s update available",
                "There are %s updates available",
                upd_len) % (upd_len,)
            )
            self.set_state("CRITICAL")
            self.show_alert(
                _("Sabayon updates available"),
                ngettext("There is <b>%s</b> update available",
                    "There are <b>%s</b> updates available",
                    upd_len) % (upd_len,),
                urgency = "critical",
                force = self.manual_check_triggered
            )
        else:
            # all fine, no updates
            self.update_tooltip(_("Your Sabayon is up-to-date"))
            self.set_state("OKAY")
            self.show_alert(_("Your Sabayon is up-to-date"),
                _("No updates available at this time, cool!"),
                force = self.manual_check_triggered
            )

        self.manual_check_triggered = False

    def updating_signal(self):
        if not config.settings['APPLET_ENABLED']:
            return

        # all fine, no updates
        self.update_tooltip(_("Repositories are being updated"))
        self.show_alert(_("Sabayon repositories status"),
            _("Repositories are being updated automatically")
        )

    def is_system_on_batteries(self):
        """
        Return whether System is running on batteries.

        @return: True, if running on batteries
        @rtype: bool
        """
        ac_powa_exec = "/usr/bin/on_ac_power"
        if not os.access(ac_powa_exec, os.X_OK):
            return False
        ex_rc = os.system(ac_powa_exec)
        if ex_rc:
            return True
        return False

    def send_check_updates_signal(self, widget=None, startup_check=False):

        # enable applet if disabled
        skip_tc = False
        if not config.settings['APPLET_ENABLED']:
            self.enable_applet(do_check = False)
            skip_tc = True

        # avoid flooding
        cur_t = time.time()
        if ((cur_t - self.last_trigger_check_t) < 15) and (not skip_tc):
            # ignore
            return
        self.last_trigger_check_t = cur_t

        if self._dbus_service_available:
            if startup_check:
                self._hello()
            else:
                self._update_repositories()
            self.manual_check_triggered = True

    def set_state(self, new_state, use_busy_icon = 0):

        if not new_state in config.APPLET_STATES:
            raise AttributeError("Error: invalid state %s" % new_state)

        if new_state == "OKAY":
            self.change_icon("okay")
        elif new_state == "BUSY":
            self.change_icon("busy")
        elif new_state == "CRITICAL":
            self.change_icon("critical")
        elif new_state == "DISABLE":
            self.change_icon("disable")
        elif new_state == "ERROR":
            self.change_icon("error")
        self.current_state = new_state

    def get_menu_image(self, name):

        if name == "update_now":
            pix = self.icons.best_match("pm", 22)
        elif name == "check_now":
            pix = self.icons.best_match("okay", 22)
        elif name in ["web_panel", "web_site"]:
            pix = self.icons.best_match("web", 22)
        elif name == "configure_applet":
            pix = self.icons.best_match("configuration", 22)
        elif name == "disable_applet":
            pix = self.icons.best_match("disable", 22)
        elif name == "enable_applet":
            pix = self.icons.best_match("okay", 22)
        else:
            pix = self.icons.best_match("busy", 22)

        return pix

    def load_packages_url(self, *data):
        self.load_url(etpConst['packages_website_url'])

    def load_website(self, *data):
        self.load_url(etpConst['distro_website_url'])

    def load_url(self, url):
        task = ParallelTask(
            subprocess.call, ['xdg-open', url])
        task.daemon = True
        task.start()

    def launch_package_manager(self, *data):
        task = ParallelTask(subprocess.call, ["/usr/bin/rigo"])
        task.daemon = True
        task.start()

    def disable_applet(self):
        self.update_tooltip(_("Updates Notification Applet Disabled"))
        self.set_state("DISABLE")
        config.settings['APPLET_ENABLED'] = 0
        config.save_settings(config.settings)
        return True

    def enable_applet(self, do_check = True):
        if not self._dbus_service_available:
            self.show_service_not_available()
            return False
        self.update_tooltip(_("Updates Notification Applet Enabled"))
        self.set_state("OKAY")
        config.settings['APPLET_ENABLED'] = 1
        config.save_settings(config.settings)
        if self._dbus_service_available and do_check:
            self.send_check_updates_signal()
        return True

    def applet_doubleclick(self):
        if not self.current_state in [ "OKAY", "ERROR", "CRITICAL" ]:
            return
        self.trigger_notice_window()

    def trigger_notice_window(self):
        if not self.notice_window_shown:
            self.show_notice_window()
        else:
            self.hide_notice_window()

    def exit_applet(self, *args):
        self.close_service()
        raise SystemExit(0)

    def close_service(self):
        entropy.tools.kill_threads()
