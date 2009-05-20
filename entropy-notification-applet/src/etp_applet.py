# -*- coding: utf-8 -*-
"""
    # DESCRIPTION:
    # Entropy updates Notification Applet

    Copyright (C) 2007-2009 Fabio Erculiani
    Forking RHN Applet

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

# sys imports
import os
import sys
import time
import subprocess
import gnome
import gnome.ui
import gtk
import gobject
import pynotify
import dbus
import dbus.exceptions
import dbus.mainloop.glib

# applet imports
import etp_applet_config
from etp_applet_components import AppletNoticeWindow, AppletAboutWindow, \
    AppletErrorDialog, AppletExceptionDialog, AppletIconPixbuf

# Entropy imports
from entropy.i18n import _
from entropy.exceptions import IncorrectParameter, OnlineMirrorError
import entropy.tools as entropyTools
from entropy.client.interfaces import Client
from entropy.const import etpConst
from entropy.core import SystemSettings

class Entropy(Client):

    def init_singleton(self, appletInterface):
        Client.init_singleton(self, noclientdb = True)
        self.connect_progress_objects(appletInterface)
        self.nocolor()

    def connect_progress_objects(self, appletInterface):
        self.i = appletInterface
        self.progress_tooltip = self.i.update_tooltip
        self.progress_tooltip_message_title = _("Updates Notification")
        self.appletCreateNotification()
        self.applet_last_message = ''

    def appletCreateNotification(self):
        self.progress_tooltip_notification = pynotify.Notification(
            self.progress_tooltip_message_title,"Hello world")
        self.progress_tooltip_notification.set_timeout(3000)

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
        pynotify.init("XY")
        self.progress_tooltip_notification.update(
            self.progress_tooltip_message_title,message)
        self.progress_tooltip_notification.attach_to_status_icon(
            self.i.status_icon)
        self.progress_tooltip_notification.show()


class EntropyApplet:

    def __init__(self):

        self.debug = False
        if "--debug" in sys.argv:
            self.debug = True

        self.animator = None
        self.client = None
        self.notice_window = None
        self.error_dialog = None
        self.error_threshold = 0
        self.about_window = None
        self.last_error = None
        self.package_updates = []
        self.last_alert = None
        self.tooltip_text = ""
        self.last_trigger_check_t = 0.0
        gnome.program_init("entropy-notifier", etpConst['entropyversion'])

        self.session = gnome.ui.master_client()
        if self.session:
            gtk.Object.connect(self.session, "save-yourself", self.save_yourself)
            gtk.Object.connect(self.session, "die", self.exit_applet)

        self.never_viewed_notices = 1
        self.current_image = None
        self.current_state = None
        self.old_critical_text = None

        self.icons = AppletIconPixbuf()

        self.icons.add_file("okay", "applet-okay.png")
        self.icons.add_file("error", "applet-error.png")
        self.icons.add_file("busy", "applet-busy.png")
        self.icons.add_file("critical", "applet-critical.png")
        self.icons.add_file("disable", "applet-disable.png")
        self.icons.add_file("sulfur","sulfur.png")
        self.icons.add_file("about","applet-about.png")
        self.icons.add_file("web","applet-web.png")
        self.icons.add_file("configuration","applet-configuration.png")
        self.applet_size = 22

        menu_items = (
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
            ("about", _("_About"), _("About..."), self.about),
            ("exit", _("_Exit"), _("Exit"), self.exit_applet),
            )

        self.menu = gtk.Menu()
        self.menu_items = {}
        for i in menu_items:
            if i is None:
                self.menu.add(gtk.SeparatorMenuItem())
            else:
                sid = None
                myid = i[0]
                if myid == "exit":
                    sid = "gtk-quit"
                if sid:
                    w = gtk.ImageMenuItem(stock_id = sid)
                else:
                    w = gtk.ImageMenuItem(i[1])
                    self.set_menu_image(w, myid)
                self.menu_items[myid] = w
                w.connect('activate', i[3])
                w.show()
                self.menu.add(w)

        self.menu.show_all()

        self.status_icon = gtk.status_icon_new_from_pixbuf(
            self.icons.best_match("okay",22))
        self.status_icon.connect("popup-menu", self.applet_face_click)
        self.status_icon.connect("activate", self.applet_face_click2)

        # Entropy dbus connection init
        self.__dbus_init_error_msg = 'Unknown error'
        self.__dbus_interface = "org.entropy.Client"
        self.__dbus_path = "/notifier"
        self.__signal_name = "signal_updates"
        self.__updating_signal_name = "signal_updating"
        self._dbus_service_available = self.setup_dbus()

        if etp_applet_config.settings['APPLET_ENABLED'] and \
            self._dbus_service_available:
            self.enable_applet(do_check = False)
        else:
            self.disable_applet()
        if not self._dbus_service_available:
            self.show_service_not_available()
        else:
            self.show_service_available()
            self.do_first_check()


    def setup_dbus(self):
        tries = 5
        while tries:
            dbus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default = True)
            self.__system_bus = dbus.SystemBus(mainloop = dbus_loop)
            try:
                self.__entropy_dbus_object = self.__system_bus.get_object(
                    self.__dbus_interface, self.__dbus_path
                )
                self.__entropy_dbus_object.connect_to_signal(
                    self.__signal_name, self.new_updates_signal,
                    dbus_interface = self.__dbus_interface
                )
                self.__entropy_dbus_object.connect_to_signal(
                    self.__updating_signal_name, self.updating_signal,
                    dbus_interface = self.__dbus_interface
                )
            except dbus.exceptions.DBusException, e:
                self.__dbus_init_error_msg = unicode(e)
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
                self.__dbus_init_error_msg,
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
        if not etp_applet_config.settings['APPLET_ENABLED']:
            return
        iface = dbus.Interface(
            self.__entropy_dbus_object, dbus_interface="org.entropy.Client")
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
                urgency = "critical"
            )
        else:
            # all fine, no updates
            self.update_tooltip(_("Your Sabayon is up-to-date"))
            self.set_state("OKAY")
            self.show_alert(_("Your Sabayon is up-to-date"),
                _("No updates available at this time, cool!")
            )

    def updating_signal(self):
        if not etp_applet_config.settings['APPLET_ENABLED']:
            return

        # all fine, no updates
        self.update_tooltip(_("Repositories are being updated"))
        self.show_alert(_("Sabayon repositories status"),
            _("Repositories are being updated automatically")
        )

    def do_first_check(self):

        def _do_check():
            self.send_check_updates_signal()
            return False

        if self._dbus_service_available:
            # after 20 seconds
            gobject.timeout_add(10000, _do_check)

    def send_check_updates_signal(self, widget=None):

        # enable applet if disabled
        skip_tc = False
        if not etp_applet_config.settings['APPLET_ENABLED']:
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
                self.__entropy_dbus_object, dbus_interface="org.entropy.Client")
            iface.trigger_check()

    def close_service(self):
        if self._dbus_service_available:
            iface = dbus.Interface(
                self.__entropy_dbus_object, dbus_interface="org.entropy.Client")
            iface.close_connection()
        entropyTools.kill_threads()

    def unblink_icon_after_secs(self, secs):
        def do_unblink():
            self.status_icon.set_blinking(False)
        gobject.timeout_add(secs*1000, do_unblink)

    def set_state(self, new_state, use_busy_icon = 0):

        if not new_state in etp_applet_config.APPLET_STATES:
            raise IncorrectParameter("Error: invalid state %s" % new_state)

        self.status_icon.set_blinking(False)
        if new_state == "OKAY":
            self.change_icon("okay")
        elif new_state == "BUSY":
            if use_busy_icon:
                self.set_displayed_image("busy")
        elif new_state == "CRITICAL":
            self.status_icon.set_blinking(True)
            self.unblink_icon_after_secs(10)
            if self.never_viewed_notices:
                self.change_icon("critical")
            else:
                self.set_displayed_image("critical")
        elif new_state == "DISABLE":
            self.change_icon("disable")
        elif new_state == "ERROR":
            self.change_icon("error")
        self.current_state = new_state

    def set_menu_image(self, widget, name):
        img = gtk.Image()
        if name == "update_now":
            pix = self.icons.best_match("sulfur",22)
        elif name == "about":
            pix = self.icons.best_match("about",22)
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

        img.set_from_pixbuf(pix)
        widget.set_image(img)

    def change_icon(self, image):
        to_image = self.icons.best_match(image, self.applet_size)
        self.status_icon.set_from_pixbuf(to_image)

    def set_displayed_image(self, image):
        if isinstance(image,basestring):
            new_image = self.icons.best_match(image, self.applet_size)
        else: new_image = image
        self.current_image = new_image
        self.redraw()

    def redraw(self):
        if not self.current_image: return
        self.status_icon.set_from_pixbuf(self.current_image)
        self.status_icon.set_visible(True)

    def load_packages_url(self, *data):
        try:
            gnome.url_show("http://www.sabayon.org/packages")
        except gobject.GError:
            self.load_url("http://www.sabayon.org/packages")

    def load_website(self, *data):
        try:
            gnome.url_show("http://www.sabayon.org/")
        except gobject.GError:
            self.load_url("http://www.sabayon.org/")

    def load_url(self, url):
        subprocess.call(['xdg-open',url])

    def disable_applet(self, *args):
        self.update_tooltip(_("Updates Notification Applet Disabled"))
        self.set_state("DISABLE")
        etp_applet_config.settings['APPLET_ENABLED'] = 0
        etp_applet_config.save_settings(etp_applet_config.settings)
        self.menu_items['disable_applet'].hide()
        self.menu_items['enable_applet'].show()

    def enable_applet(self, w = None, do_check = True):
        if not self._dbus_service_available:
            self.show_service_not_available()
            return
        self.update_tooltip(_("Updates Notification Applet Enabled"))
        self.set_state("OKAY")
        etp_applet_config.settings['APPLET_ENABLED'] = 1
        etp_applet_config.save_settings(etp_applet_config.settings)
        self.menu_items['disable_applet'].show()
        self.menu_items['enable_applet'].hide()
        if self._dbus_service_available and do_check:
            self.send_check_updates_signal()

    def launch_package_manager(self, *data):
        def spawn_sulfur():
            os.execv('/usr/bin/sulfur', ['sulfur'])
        pid = os.fork()
        if pid == 0:
            spawn_sulfur()
            os._exit(0)

    def show_alert(self, title, text, urgency = None):

        if (title,text) == self.last_alert:
            return
        pynotify.init("XY")
        n = pynotify.Notification(title, text)
        if urgency == 'critical':
            n.set_urgency(pynotify.URGENCY_CRITICAL)
        elif urgency == 'low':
            n.set_urgency(pynotify.URGENCY_LOW)
        self.last_alert = (title,text)
        n.attach_to_status_icon(self.status_icon)
        n.show()

    def update_tooltip(self, tip):
        self.tooltip_text = tip
        self.status_icon.set_tooltip(tip)

    def exit_applet(self, *args):
        self.close_service()
        gtk.main_quit()
        raise SystemExit(0)

    def save_yourself(self, *args):
        if self.session:
            self.session.set_clone_command(1, ["/usr/bin/entropy-update-applet"])
            self.session.set_restart_command(1, ["/usr/bin/entropy-update-applet"])
        return True

    def about(self, *data):
        if self.about_window:
            return
        self.about_window = AppletAboutWindow(self)

    def about_dialog_closed(self):
        self.about_window = None

    def notice_window_closed(self):
        self.notice_window = None

    def error_dialog_closed(self):
        self.error_dialog = None
        self.last_error = None
        self.set_state("OKAY")
        self.update_tooltip(_("Waiting before checkin..."))

    def applet_face_click(self, icon, button, activate_time):
        if button == 3:
            self.menu.popup(None, None, None, 0, activate_time)
            return

    def applet_face_click2(self, icon):

        if not self.current_state in [ "OKAY", "ERROR", "CRITICAL" ]:
            return

        if self.last_error:
            if self.error_dialog:
                return
            self.error_dialog = AppletErrorDialog(self, self.last_error)
            return

        self.never_viewed_notices = 0
        if self.notice_window:
            self.notice_window.close_window()
            return

        if not self.notice_window:
            self.notice_window = AppletNoticeWindow(self)

        self.refresh_notice_window()

    def refresh_notice_window(self):

        self.notice_window.clear_window()
        if not self.package_updates:
            return

        entropy_ver = None
        packages = []
        for atom in self.package_updates:

            key = entropyTools.dep_getkey(atom)
            avail_rev = entropyTools.dep_get_entropy_revision(atom)
            avail_tag = entropyTools.dep_gettag(atom)
            my_pkg = entropyTools.remove_entropy_revision(atom)
            my_pkg = entropyTools.remove_tag(my_pkg)
            pkgcat, pkgname, pkgver, pkgrev = entropyTools.catpkgsplit(my_pkg)
            ver = pkgver
            if pkgrev != "r0":
                ver += "-%s" % (pkgrev,)
            if avail_tag:
                ver += "#%s" % (avail_tag,)
            if avail_rev:
                ver += "~%s" % (avail_tag,)

            if key == "sys-apps/entropy":
                entropy_ver = ver

            packages.append((key, ver,))


        self.notice_window.fill(packages)

        critical_text = []
        if entropy_ver != None:
            msg = "%s <b>sys-apps/entropy</b> %s, %s <b>%s</b>. %s." % (
                _("Your system currently has an outdated version of"),
                _("installed"),
                _("the latest available version is"),
                entropy_ver,
                _("It is recommended that you upgrade to the latest before updating any other packages")
            )
            critical_text.append(msg)

        if critical_text:
            if self.old_critical_text != critical_text:
                self.notice_window.set_critical('<br><br>'.join(critical_text), critical_active = 1)
            else:
                self.notice_window.set_critical('<br><br>'.join(critical_text), critical_active = 0)
            self.old_critical_text = critical_text
        else:
            self.notice_window.remove_critical()


    def set_ignored(self, name, new_value):
        self.never_viewed_notices = 0
