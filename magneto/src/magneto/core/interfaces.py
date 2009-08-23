"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) core interfaces}

"""

# System imports
import sys
import time
import subprocess
import dbus
import dbus.exceptions

# Entropy imports
from entropy.client.interfaces import Client
import entropy.tools as entropyTools
from entropy.i18n import _

# Magneto imports
from magneto.core import config

class MagnetoCoreUI:

    """
    Methods in this class are inherited by MagnetoCore and should be
    reimplemented by its subclasses.
    """

    def startup(self):
        """
        Graphical Interface startup method.
        Must be reimplemented.
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def update_tooltip(self, tip):
        """
        Update applet tooltip

        @param tip: new tooltip text
        @type tip: string
        """
        raise NotImplementedError

    def change_icon(self, image):
        """
        Update applet icon
        """
        raise NotImplementedError

    def applet_context_menu(self):
        """
        When context menu action is triggered
        """
        raise NotImplementedError

    def show_notice_window(self):
        """
        Show the Updates Notification window
        """
        raise NotImplementedError

    def hide_notice_window(self):
        """
        Hide the Updates Notification window
        """
        raise NotImplementedError


class MagnetoCore(MagnetoCoreUI):
    """
    Magneto base UI interface, must be subclassed to make it support Qt/GTK
    interfaces.
    """
    def __init__(self, icon_loader_class, main_loop_class):

        if "--debug" not in sys.argv:
            import signal
            signal.signal(signal.SIGINT, signal.SIG_DFL)

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
        self.icons.add_file("sulfur","sulfur.png")
        self.icons.add_file("web","applet-web.png")
        self.icons.add_file("configuration","applet-configuration.png")
        self.applet_size = 22

        # Dbus variables
        self._dbus_init_error_msg = 'Unknown error'
        self._dbus_interface = "org.entropy.Client"
        self._dbus_path = "/notifier"
        self._signal_name = "signal_updates"
        self._updating_signal_name = "signal_updating"

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
            ("exit", _("_Exit"), _("Exit"), self.exit_applet),
        )

        self._main_loop_class = main_loop_class

    def setup_dbus(self):
        """
        Dbus Setup method.
        """
        tries = 5
        while tries:
            dbus_loop = self._main_loop_class(set_as_default = True)
            self._system_bus = dbus.SystemBus(mainloop = dbus_loop)
            try:
                self._entropy_dbus_object = self._system_bus.get_object(
                    self._dbus_interface, self._dbus_path
                )
                self._entropy_dbus_object.connect_to_signal(
                    self._signal_name, self.new_updates_signal,
                    dbus_interface = self._dbus_interface
                )
                self._entropy_dbus_object.connect_to_signal(
                    self._updating_signal_name, self.updating_signal,
                    dbus_interface = self._dbus_interface
                )
            except dbus.exceptions.DBusException, e:
                self._dbus_init_error_msg = unicode(e)
                # service not avail
                tries -= 1
                time.sleep(2)
                continue
            return True
        entropyTools.print_traceback()
        return False

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

    def show_service_available(self):
        self.show_alert(
            _("Sabayon updates service loaded"),
            "%s: %s." % (
                _("Entropy DBus service loaded"),
                _("your Sabayon will notify you once updates are available"),
            )
        )

    def new_updates_signal(self):
        if not config.settings['APPLET_ENABLED']:
            return
        iface = dbus.Interface(
            self._entropy_dbus_object, dbus_interface="org.entropy.Client")
        updates = iface.get_updates_atoms()
        avail = [str(x) for x in updates]
        del self.package_updates[:]
        self.package_updates.extend(avail)
        upd_len = len(updates)

        if upd_len:
            self.update_tooltip("%s %s %s" % (
                _("There are"),
                upd_len,
                _("updates available"),)
            )
            self.set_state("CRITICAL")
            self.show_alert(
                _("Sabayon updates available"),
                "%s %s %s" % (
                    _("There are"),
                    "<b>%s</b>" % (upd_len,),
                    _("updates available"),
                ),
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

    def is_system_changed(self):

        # enable applet if disabled
        if not config.settings['APPLET_ENABLED']:
            return False

        # dbus daemon not available
        if not self._dbus_service_available:
            return False

        iface = dbus.Interface(
            self._entropy_dbus_object, dbus_interface="org.entropy.Client")
        return iface.is_system_changed()

    def send_check_updates_signal(self, widget=None):

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
            iface = dbus.Interface(
                self._entropy_dbus_object, dbus_interface="org.entropy.Client")
            iface.trigger_check()
            self.manual_check_triggered = True

    def set_state(self, new_state, use_busy_icon = 0):

        if not new_state in config.APPLET_STATES:
            raise IncorrectParameter("Error: invalid state %s" % new_state)

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
            pix = self.icons.best_match("sulfur",22)
        elif name in ["web_panel","web_site"]:
            pix = self.icons.best_match("web",22)
        elif name == "configure_applet":
            pix = self.icons.best_match("configuration",22)
        elif name == "disable_applet":
            pix = self.icons.best_match("disable",22)
        elif name == "enable_applet":
            pix = self.icons.best_match("okay",22)
        else:
            pix = self.icons.best_match("busy",22)

        return pix

    def load_packages_url(self, *data):
        self.load_url("http://www.sabayon.org/packages")

    def load_website(self, *data):
        self.load_url("http://www.sabayon.org/")

    def load_url(self, url):
        subprocess.call(['xdg-open', url])

    def launch_package_manager(self, *data):
        subprocess.call('sulfur &', shell = True)

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
        if self._dbus_service_available:
            iface = dbus.Interface(
                self._entropy_dbus_object, dbus_interface="org.entropy.Client")
            iface.close_connection()
        entropyTools.kill_threads()


class Entropy(Client):

    """
    @deprecated
    """

    def init_singleton(self, magneto):
        Client.init_singleton(self, noclientdb = True)
        self.__magneto = magneto
        self.progress_tooltip = self.__magneto.update_tooltip
        self.progress_tooltip_message_title = _("Updates Notification")
        self.applet_last_message = ''
        self.nocolor()

    def updateProgress(self, text, header = "", footer = "", back = False,
            importance = 0, type = "info", count = [], percent = False):

        count_str = ""
        if count:
            if percent:
                count_str = str(int(round((float(count[0])/count[1])*100,1)))+"% "
            else:
                count_str = "(%s/%s) " % (str(count[0]),str(count[1]),)

        message = count_str+_(text)
        #if importance in (1,2):
        if importance == 2:
            self.progress_tooltip_message_title = message
            self.__do_applet_print(self.applet_last_message)
        else:
            self.__do_applet_print(message)

    def __do_applet_print(self, message):
        self.applet_last_message = message
        self.__magneto.show_alert(self.progress_tooltip_message_title,
            message)