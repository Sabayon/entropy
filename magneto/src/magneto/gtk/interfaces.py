# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) GTK application}

"""

# sys imports
import os
import sys
import time
import subprocess
import gtk
import gobject
import pynotify

# applet imports
from magneto.core import config
from magneto.core.interfaces import MagnetoCore
from magneto.gtk.components import AppletNoticeWindow, AppletIconPixbuf

# Entropy imports
from entropy.i18n import _
import entropy.tools as entropyTools

class Magneto(MagnetoCore):

    def __init__(self):

        from dbus.mainloop.glib import DBusGMainLoop
        MagnetoCore.__init__(self, icon_loader_class = AppletIconPixbuf,
            main_loop_class = DBusGMainLoop)

        self.__setup_gtk_app()

    def __setup_gtk_app(self):

        self.menu = gtk.Menu()
        self.menu_items = {}
        for i in self._menu_item_list:
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
                    pix = self.get_menu_image(myid)
                    img = gtk.Image()
                    img.set_from_pixbuf(pix)
                    w.set_image(img)
                self.menu_items[myid] = w
                w.connect('activate', i[3])
                w.show()
                self.menu.add(w)

        self.menu.show_all()

        self.status_icon = gtk.status_icon_new_from_pixbuf(
            self.icons.best_match("okay",22))
        self.status_icon.connect("popup-menu", self.applet_context_menu)
        self.status_icon.connect("activate", self.applet_doubleclick)


    def __do_first_check(self):

        def _do_check():
            self.send_check_updates_signal()
            return False

        if self._dbus_service_available:
            # after 20 seconds
            gobject.timeout_add(10000, _do_check)

    def startup(self):

        self._dbus_service_available = self.setup_dbus()
        if config.settings['APPLET_ENABLED'] and \
            self._dbus_service_available:
            self.enable_applet(do_check = False)
        else:
            self.disable_applet()
        if not self._dbus_service_available:
            self.show_service_not_available()
        else:
            self.show_service_available()
            self.__do_first_check()

        # Notice Window instance
        self._notice_window = AppletNoticeWindow(self)

        # enter main loop
        gobject.threads_init()
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()

    def close_service(self):
        MagnetoCore.close_service(self)
        gtk.main_quit()

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

    def show_alert(self, title, text, urgency = None):

        def do_show():
            if (title,text) == self.last_alert:
                return False
            pynotify.init("XY")
            n = pynotify.Notification(title, text)
            if urgency == 'critical':
                n.set_urgency(pynotify.URGENCY_CRITICAL)
            elif urgency == 'low':
                n.set_urgency(pynotify.URGENCY_LOW)
            self.last_alert = (title,text)
            n.attach_to_status_icon(self.status_icon)
            n.show()
            return False

        gobject.timeout_add(0, do_show)

    def update_tooltip(self, tip):
        self.tooltip_text = tip
        self.status_icon.set_tooltip(tip)

    def applet_context_menu(self, icon, button, activate_time):
        if button == 3:
            self.menu.popup(None, None, None, 0, activate_time)
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

        critical_txt = ''
        if entropy_ver is not None:
            critical_txt = "%s <b>sys-apps/entropy</b> %s, %s <b>%s</b>. %s." % (
                _("Your system currently has an outdated version of"),
                _("installed"),
                _("the latest available version is"),
                entropy_ver,
                _("It is recommended that you upgrade to the latest before updating any other packages")
            )

        self._notice_window.populate(packages, critical_txt)
        self._notice_window.show()
        self.notice_window_shown = True
