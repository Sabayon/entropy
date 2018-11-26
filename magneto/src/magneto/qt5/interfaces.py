# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) KDE application}

"""
import os
import sys

# PyQt5 imports
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, \
    QAction, QDialog

# Magneto imports
from _entropy.magneto.core import config
from _entropy.magneto.core.interfaces import MagnetoCore
from _entropy.magneto.qt5.components import AppletNoticeWindow

# Entropy imports
from entropy.i18n import _
from entropy.const import const_debug_write
import entropy.dep


class Magneto(MagnetoCore):

    """
    Magneto Updates Notification Applet class.
    """

    def __init__(self):
        self._app = QApplication([sys.argv[0]])

        from dbus.mainloop.pyqt5 import DBusQtMainLoop
        super(Magneto, self).__init__(main_loop_class = DBusQtMainLoop)

        self._window = QSystemTrayIcon(self._app)
        icon_name = self.icons.get("okay")
        self._window.setIcon(QIcon.fromTheme(icon_name))
        self._window.activated.connect(self._applet_activated)

        self._menu = QMenu(_("Magneto Entropy Updates Applet"))
        self._window.setContextMenu(self._menu)

        self._menu_items = {}
        for item in self._menu_item_list:
            if item is None:
                self._menu.addSeparator()
                continue

            myid, _unused, mytxt, myslot_func = item
            name = self.get_menu_image(myid)
            action_icon = QIcon.fromTheme(name)

            w = QAction(action_icon, mytxt, self._window,
                        triggered=myslot_func)
            self._menu_items[myid] = w
            self._menu.addAction(w)

        self._menu.hide()

    def _first_check(self):
        def _do_check():
            self.send_check_updates_signal(startup_check = True)
            return False

        if self._dbus_service_available:
            const_debug_write("_first_check", "spawning check.")
            QTimer.singleShot(10000, _do_check)

    def startup(self):
        self._dbus_service_available = self.setup_dbus()
        if config.settings["APPLET_ENABLED"] and \
            self._dbus_service_available:
            self.enable_applet(do_check = False)
            const_debug_write("startup", "applet enabled, dbus service available.")
        else:
            const_debug_write("startup", "applet disabled.")
            self.disable_applet()
        if not self._dbus_service_available:
            const_debug_write("startup", "dbus service not available.")
            QTimer.singleShot(30000, self.show_service_not_available)
        else:
            const_debug_write("startup", "spawning first check.")
            self._first_check()

        # Notice Window instance
        self._notice_window = AppletNoticeWindow(self)

        self._window.show()

        # Enter main loop
        self._app.exec_()

    def close_service(self):
        super(Magneto, self).close_service()
        self._app.quit()

    def change_icon(self, icon_name):
        name = self.icons.get(icon_name)
        self._window.setIcon(QIcon.fromTheme(name))

    def disable_applet(self, *args):
        super(Magneto, self).disable_applet()
        self._menu_items["disable_applet"].setEnabled(False)
        self._menu_items["enable_applet"].setEnabled(True)

    def enable_applet(self, w = None, do_check = True):
        done = super(Magneto, self).enable_applet(do_check = do_check)
        if done:
            self._menu_items["disable_applet"].setEnabled(True)
            self._menu_items["enable_applet"].setEnabled(False)

    def show_alert(self, title, text, urgency = None, force = False,
                   buttons = None):

        # NOTE: there is no support for buttons via QSystemTrayIcon.

        if ((title, text) == self.last_alert) and not force:
            return

        def _action_activate_cb(action_num):
            if not buttons:
                return

            try:
                action_info = buttons[action_num - 1]
            except IndexError:
                return

            _action_id, _button_name, button_callback = action_info
            button_callback()

        def do_show():
            if not self._window.supportsMessages():
                const_debug_write("show_alert", "messages not supported.")
                return

            icon_id = QSystemTrayIcon.Information
            if urgency == "critical":
                icon_id = QSystemTrayIcon.Critical

            self._window.showMessage(title, text, icon_id)
            self.last_alert = (title, text)

        QTimer.singleShot(0, do_show)

    def update_tooltip(self, tip):
        def do_update():
            self._window.setToolTip(tip)
        QTimer.singleShot(0, do_update)

    def applet_context_menu(self):
        """No action for now."""

    def _applet_activated(self, reason):
        const_debug_write("applet_activated", "Applet activated: %s" % reason)
        if reason == QSystemTrayIcon.DoubleClick:
            const_debug_write("applet_activated", "Double click event.")
            self.applet_doubleclick()

    def hide_notice_window(self):
        self.notice_window_shown = False
        self._notice_window.hide()

    def show_notice_window(self):

        if self.notice_window_shown:
            const_debug_write("show_notice_window", "Notice window already shown.")
            return

        if not self.package_updates:
            const_debug_write("show_notice_window", "No computed updates.")
            return

        entropy_ver = None
        packages = []
        for atom in self.package_updates:

            key = entropy.dep.dep_getkey(atom)
            avail_rev = entropy.dep.dep_get_entropy_revision(atom)
            avail_tag = entropy.dep.dep_gettag(atom)
            my_pkg = entropy.dep.remove_entropy_revision(atom)
            my_pkg = entropy.dep.remove_tag(my_pkg)
            pkgcat, pkgname, pkgver, pkgrev = entropy.dep.catpkgsplit(my_pkg)
            ver = pkgver
            if pkgrev != "r0":
                ver += "-%s" % (pkgrev,)
            if avail_tag:
                ver += "#%s" % (avail_tag,)
            if avail_rev:
                ver += "~%s" % (avail_tag,)

            if key == "sys-apps/entropy":
                entropy_ver = ver

            packages.append("%s (%s)" % (key, ver,))

        critical_msg = ""
        if entropy_ver is not None:
            critical_msg = "%s <b>sys-apps/entropy</b> %s, %s <b>%s</b>. %s." % (
                _("Your system currently has an outdated version of"),
                _("installed"),
                _("the latest available version is"),
                entropy_ver,
                _("It is recommended that you upgrade to "
                  "the latest before updating any other packages")
            )

        self._notice_window.populate(packages, critical_msg)

        self._notice_window.show()
        self.notice_window_shown = True
