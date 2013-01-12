# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Updates Notification Applet (Magneto) KDE application}

"""
import sys

# PyQt4 imports
from PyQt4.QtCore import QTimer, SIGNAL
from PyQt4.QtGui import QIcon

# PyKDE4 imports
from PyKDE4.kdecore import KAboutData, KCmdLineArgs, ki18n
from PyKDE4.kdeui import KApplication, KSystemTrayIcon, KIcon, KMenu, KAction, \
    KNotification

# Magneto imports
from magneto.core import config
from magneto.core.interfaces import MagnetoCore
from magneto.kde.components import AppletNoticeWindow, AppletIconPixbuf

# Entropy imports
from entropy.i18n import _
import entropy.dep


class Magneto(MagnetoCore):

    """
    Magneto Updates Notification Applet class.
    """

    def __init__(self):

        app_name    = "magneto"
        catalog     = ""
        prog_name   = ki18n("Magneto")
        version     = "1.0"
        description = ki18n("Magneto Updates Notification Applet")
        lic         = KAboutData.License_GPL
        cright      = ki18n("(c) 2009 Fabio Erculiani")
        text        = ki18n("none")
        home_page   = "www.sabayon.org"
        bug_mail    = "fabio.erculiani@sabayon.org"

        self._kabout = KAboutData (app_name, catalog, prog_name, version,
            description, lic, cright, text, home_page, bug_mail)

        argv = [sys.argv[0]]
        KCmdLineArgs.init(argv, self._kabout)
        self._app = KApplication()

        from dbus.mainloop.qt import DBusQtMainLoop
        MagnetoCore.__init__(self, icon_loader_class = AppletIconPixbuf,
            main_loop_class = DBusQtMainLoop)

        self.__setup_kde_app()

    def __setup_kde_app(self):
        # setup Systray application
        qpix = self.icons.best_match("okay", 22)
        qicon = QIcon(qpix)
        self.status_icon = KIcon(qicon)
        self._window = KSystemTrayIcon(self.status_icon)
        self._window.connect(self._window,
            SIGNAL("activated(QSystemTrayIcon::ActivationReason)"),
            self.applet_activated)
        self._menu = KMenu(_("Magneto Entropy Updates Applet"))
        self._window.setContextMenu(self._menu)

        self._menu_items = {}
        for i in self._menu_item_list:
            if i is None:
                self._menu.addSeparator()
            else:
                myid, mytxt, myslot_func = i[0], i[2], i[3]
                if myid == "exit":
                    action_icon = KIcon(myid)
                else:
                    qicon = QIcon(self.get_menu_image(myid))
                    action_icon = KIcon(qicon)
                w = KAction(action_icon, mytxt, self._menu)
                self._menu_items[myid] = w
                self._window.connect(w, SIGNAL('triggered()'), myslot_func)
                self._menu.addAction(w)

        self._menu.hide()

    def __do_first_check(self):

        def _do_check():
            self.send_check_updates_signal(startup_check = True)
            return False

        if self._dbus_service_available:
            QTimer.singleShot(10000, _do_check)

    def startup(self):
        """
        Start user interface.
        """

        self._dbus_service_available = self.setup_dbus()
        if config.settings['APPLET_ENABLED'] and \
            self._dbus_service_available:
            self.enable_applet(do_check = False)
        else:
            self.disable_applet()
        if not self._dbus_service_available:
            QTimer.singleShot(30000, self.show_service_not_available)
        else:
            self.__do_first_check()

        # Notice Window instance
        self._notice_window = AppletNoticeWindow(self)

        # Enter main loop
        self._window.show()
        self._menu.show()
        self._app.exec_()


    def close_service(self):
        MagnetoCore.close_service(self)
        self._app.quit()

    def change_icon(self, image):
        qpixmap = self.icons.best_match(image, self.applet_size)
        qicon = QIcon(qpixmap)
        self._window.setIcon(qicon)
        self.status_icon = qicon

    def disable_applet(self, *args):
        MagnetoCore.disable_applet(self)
        self._menu_items['disable_applet'].setEnabled(False)
        self._menu_items['enable_applet'].setEnabled(True)

    def enable_applet(self, w = None, do_check = True):
        done = MagnetoCore.enable_applet(self, do_check = do_check)
        if done:
            self._menu_items['disable_applet'].setEnabled(True)
            self._menu_items['enable_applet'].setEnabled(False)


    def show_alert(self, title, text, urgency = None, force = False):

        if ((title, text) == self.last_alert) and not force:
            return

        def do_show():
            notification = KNotification("Updates")
            notification.setFlags(KNotification.CloseOnTimeout)
            notification.setText("<b>%s</b><br/>%s" % (title, text,))
            if urgency == 'critical':
                notification.setPixmap(self.icons.best_match("critical", 22))
            else:
                notification.setPixmap(self.icons.best_match("okay", 22))
            #print "sending event: %s: %s" % (title, text,)
            notification.sendEvent()
            self.last_alert = (title, text)

        # thread safety
        QTimer.singleShot(0, do_show)

    def update_tooltip(self, tip):
        def do_update():
            self._window.setToolTip(tip)
        QTimer.singleShot(0, do_update)

    def applet_context_menu(self):
        """
        No action for now.
        """
        pass

    def applet_activated(self, activation_reason):

        if activation_reason == KSystemTrayIcon.DoubleClick:
            self.applet_doubleclick()

        elif activation_reason == KSystemTrayIcon.Context:
            self.applet_context_menu()

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
                _("It is recommended that you upgrade to the latest before updating any other packages")
            )

        self._notice_window.populate(packages, critical_msg)

        self._notice_window.show()
        self.notice_window_shown = True
