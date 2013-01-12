# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) GTK3 application}

"""

# sys imports
import os
import sys
import time
import subprocess

# applet imports
from magneto.core import config
from magneto.core.interfaces import MagnetoCore
from magneto.gtk3.components import AppletNoticeWindow, AppletIconPixbuf

# Entropy imports
from entropy.i18n import _
import entropy.dep

from gi.repository import Gtk, GObject, GLib, Gdk, Notify

class Magneto(MagnetoCore):

    def __init__(self):

        from dbus.mainloop.glib import DBusGMainLoop
        MagnetoCore.__init__(self, icon_loader_class = AppletIconPixbuf,
            main_loop_class = DBusGMainLoop)

        self.__setup_gtk_app()

    def __setup_gtk_app(self):

        self.menu = Gtk.Menu()
        self.menu_items = {}
        for i in self._menu_item_list:
            if i is None:
                self.menu.add(Gtk.SeparatorMenuItem())
            else:
                sid = None
                myid = i[0]
                if myid == "exit":
                    sid = "gtk-quit"
                if sid:
                    w = Gtk.ImageMenuItem(stock_id = sid)
                else:
                    w = Gtk.ImageMenuItem(i[1])
                    w.set_use_underline(True)
                    pix = self.get_menu_image(myid)
                    img = Gtk.Image()
                    img.set_from_pixbuf(pix)
                    w.set_image(img)
                self.menu_items[myid] = w
                w.connect('activate', i[3])
                w.show()
                self.menu.add(w)

        self.menu.show_all()

        self.status_icon = Gtk.StatusIcon.new_from_pixbuf(
            self.icons.best_match("okay", 22))
        self.status_icon.connect("popup-menu", self.applet_context_menu)
        self.status_icon.connect("activate", self.applet_doubleclick)

    def __do_first_check(self):

        def _do_check():
            self.send_check_updates_signal(startup_check = True)
            return False

        if self._dbus_service_available:
            # after 10 seconds
            GObject.timeout_add(10000, _do_check)

    def startup(self):

        self._dbus_service_available = self.setup_dbus()
        if config.settings['APPLET_ENABLED'] and \
            self._dbus_service_available:
            self.enable_applet(do_check = False)
        else:
            self.disable_applet()
        if not self._dbus_service_available:
            GObject.timeout_add(30000, self.show_service_not_available)
        else:
            self.__do_first_check()

        # Notice Window instance
        self._notice_window = AppletNoticeWindow(self)

        # enter main loop
        GLib.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()

    def close_service(self):
        MagnetoCore.close_service(self)
        GObject.timeout_add(0, Gtk.main_quit)

    def change_icon(self, image):
        to_image = self.icons.best_match(image, self.applet_size)
        self.status_icon.set_from_pixbuf(to_image)

    def disable_applet(self, *args):
        MagnetoCore.disable_applet(self)
        self.menu_items['disable_applet'].hide()
        self.menu_items['enable_applet'].show()

    def enable_applet(self, w = None, do_check = True):
        done = MagnetoCore.enable_applet(self, do_check = do_check)
        if done:
            self.menu_items['disable_applet'].show()
            self.menu_items['enable_applet'].hide()

    def applet_doubleclick(self, widget):
        return MagnetoCore.applet_doubleclick(self)

    def show_alert(self, title, text, urgency = None, force = False):

        def do_show():
            if ((title, text) == self.last_alert) and not force:
                return False
            Notify.init(_("System Updates"))
            n = Notify.Notification.new(
                title, text, "dialog-information")
            if urgency == 'critical':
                n.set_urgency(Notify.Urgency.CRITICAL)
            elif urgency == 'low':
                n.set_urgency(Notify.Urgency.LOW)
            self.last_alert = (title, text)
            try:
                # this has been dropped from libnotify 0.7
                n.attach_to_status_icon(self.status_icon)
            except AttributeError:
                pass
            n.show()
            return False

        GObject.timeout_add(0, do_show)

    def update_tooltip(self, tip):
        self.tooltip_text = tip
        self.status_icon.set_tooltip_markup(tip)

    def applet_context_menu(self, icon, button, activate_time):
        if button == 3:
            self.menu.popup(None, None, None, None, 0, activate_time)
            return

    def hide_notice_window(self):
        self.notice_window_shown = False
        self._notice_window.hide()

    def show_notice_window(self):

        if self.notice_window_shown:
            return
        if not self.package_updates:
            return

        entropy_ver = None
        packages = []
        for atom in self.package_updates:

            key = entropy.dep.dep_getkey(atom)
            avail_rev = entropy.dep.dep_get_entropy_revision(atom)
            avail_tag = entropy.dep.dep_gettag(atom)
            my_pkg = entropy.dep.remove_entropy_revision(atom)
            my_pkg = entropy.dep.remove_tag(my_pkg)
            pkgcat, pkgname, pkgver, pkgrev = entropy.dep.catpkgsplit(
                my_pkg)
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

        critical_txt = ''
        if entropy_ver is not None:
            critical_txt = "%s <b>sys-apps/entropy</b> %s, %s <b>%s</b>. %s." % (
                _("Your system currently has an outdated version of"),
                _("installed"),
                _("the latest available version is"),
                entropy_ver,
                _("It is recommended that you upgrade to"
                  " the latest before updating any other packages")
            )

        self._notice_window.populate(packages, critical_txt)
        self._notice_window.show()
        self.notice_window_shown = True
