# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 1999-2002 Red Hat, Inc. All Rights Reserved.
# Distributed under GPL version 2.
#
# Author: Chip Turner
#
# def help added by Tammy Fox
#
# $Id: rhn_applet.py,v 1.114 2003/11/09 16:56:33 veillard Exp $
import os
import sys
import time
import threading
import subprocess

import gnome
import gnome.ui
# from msw to avoid odd bugs in some pygtk builds
import gtk
import gobject
import gtk.gdk
import pynotify

import etp_applet_animation
from etp_applet_dialogs import \
     rhnAppletNoticeWindow, \
     rhnRegistrationPromptDialog, \
     rhnAppletAboutWindow, \
     rhnAppletFirstTimeDruid, \
     rhnAppletErrorDialog, \
     rhnAppletExceptionDialog
import etp_applet_config

# Entropy imports
from entropy.misc import TimeScheduled, ParallelTask
from entropy.i18n import _
from entropy.exceptions import *
import entropy.tools as entropyTools
from entropy.client.interfaces import Client as EquoInterface
from entropy.client.interfaces import Repository as RepoInterface
from entropy.transceivers import urlFetcher
from entropy.const import etpConst, etpRepositories

class Entropy(EquoInterface):

    def init_singleton(self, appletInterface):
        EquoInterface.init_singleton(self, noclientdb = True)
        self.connect_progress_objects(appletInterface)
        self.nocolor()

    def connect_progress_objects(self, appletInterface):
        self.i = appletInterface
        self.progress_tooltip = self.i.update_tooltip
        self.updateProgress = self.appletUpdateProgress
        self.progress_tooltip_message_title = _("Updates Notification")
        self.appletCreateNotification()
        self.urlFetcher = GuiUrlFetcher
        self.progress = self.appletPrintText # for the GuiUrlFetcher
        self.applet_last_message = ''

    def appletCreateNotification(self):
        self.progress_tooltip_notification = pynotify.Notification(self.progress_tooltip_message_title,"Hello world")
        self.progress_tooltip_notification.set_timeout(3000)

    def appletUpdateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):

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
            self.appletPrintText(self.applet_last_message)
        else:
            self.appletPrintText(message)

    def appletPrintText(self, message):
        self.applet_last_message = message
        def _appletPrintText():
            pynotify.init("XY")
            self.progress_tooltip_notification.update(self.progress_tooltip_message_title,message)
            self.progress_tooltip_notification.attach_to_status_icon(self.i.status_icon)
            self.progress_tooltip_notification.show()
        self.i.TaskQueue.append((_appletPrintText,[],{},))

class GuiUrlFetcher(urlFetcher):

    def __init__(self, *args, **kwargs):
        urlFetcher.__init__(self, *args, **kwargs)
        self.__remotesize = 0
        self.__downloadedsize = 0
        self.__datatransfer = 0

    def connect_to_gui(self, progress):
        self.progress = progress

    def handle_statistics(self, th_id, downloaded_size, total_size,
            average, old_average, update_step, show_speed, data_transfer,
            time_remaining, time_remaining_secs):
        self.__remotesize = total_size
        self.__downloadedsize = downloaded_size
        self.__datatransfer = data_transfer

    def updateProgress(self):
        self.gather = self.__downloadedsize
        message = "Fetching data %s/%s kB @ %s" % (
                                        str(round(float(self.__downloadedsize)/1024,1)),
                                        str(round(self.__remotesize,1)),
                                        str(entropyTools.bytes_into_human(self.__datatransfer))+"/sec",
                                    )
        self.progress(message)

class EntropyApplet:

    def set_state(self, new_state, use_busy_icon = 0):

        if not new_state in etp_applet_config.APPLET_STATES:
            raise IncorrectParameter("Error: invalid state %s" % new_state)

        def _set_state(new_state, use_busy_icon):
            self.status_icon.set_blinking(False)
            if new_state == "OKAY":
                self.change_icon("okay")
            elif new_state == "BUSY":
                if use_busy_icon:
                    self.set_displayed_image("busy")
            elif new_state == "CRITICAL":
                self.status_icon.set_blinking(True)
                if self.never_viewed_notices:
                    self.change_icon("critical")
                else:
                    self.set_displayed_image("critical")
            elif new_state == "NOCONSENT":
                if self.never_viewed_consent:
                    self.change_icon("noconsent")
                else:
                    self.set_displayed_image("noconsent")
            elif new_state == "DISCONNECTED":
                self.change_icon("disconnect")
            elif new_state == "DISABLE":
                self.change_icon("disable")
            elif new_state == "ERROR":
                self.change_icon("error")
            self.current_state = new_state
        if self.debug: print "queued:",_set_state
        self.TaskQueue.append((_set_state,[new_state,use_busy_icon],{},))


    def __init__(self):

        self.TaskQueueAlive = True
        self.TaskQueue = []
        self.TaskQueueId = gobject.timeout_add(200, self.task_queue_executor)

        self.debug = False
        if "--debug" in sys.argv:
            self.debug = True

        self.animator = None
        self.client = None
        self.notice_window = None
        self.rhnreg_dialog = None
        self.error_dialog = None
        self.error_threshold = 0
        self.about_window = None
        self.last_error = None
        self.last_error_is_exception = 0
        self.last_error_is_network_error = 0
        self.change_number = 0
        self.available_packages = []
        self.last_alert = None
        self.Entropy = None
        self.isWorking = False
        self.refresh_lock = threading.Lock()
        self.tooltip_text = ""
        gnome.program_init("spritz-updater", etpConst['entropyversion'])

        self.session = gnome.ui.master_client()
        if self.session:
            gtk.Object.connect(self.session, "save-yourself", self.save_yourself)
            gtk.Object.connect(self.session, "die", self.exit_applet)

        self.consent = {}
        self.never_viewed_consent = 1
        self.never_viewed_notices = 1

        self.skip_check_locked = False
        self.current_image = None
        self.refresh_timeout_tag = None
        self.current_state = None
        self.old_critical_text = None
        self.network_timeout_tag = None

        self.icons = etp_applet_animation.rhnAppletIconPixbuf()

        self.icons.add_file("okay", "applet-okay.png")
        self.icons.add_file("error", "applet-error.png")
        self.icons.add_file("busy", "applet-busy.png")
        self.icons.add_file("critical", "applet-critical.png")
        self.icons.add_file("disable", "applet-disable.png")
        self.icons.add_file("noconsent", "applet-critical.png")
        self.icons.add_file("disconnect", "applet-disconnect.png")
        self.icons.add_file("spritz","spritz.png")
        self.icons.add_file("about","applet-about.png")
        self.icons.add_file("web","applet-web.png")
        self.icons.add_file("configuration","applet-configuration.png")
        self.applet_size = 22

        menu_items = (
            ("disable_applet", _("_Disable Notification Applet"), _("Disable Notification Applet"), self.disable_applet),
            ("enable_applet", _("_Enable Notification Applet"), _("Enable Notification Applet"), self.enable_applet),
            ("check_now", _("_Check for updates"), _("Check for updates"), self.update_from_server),
            ("update_now", _("_Launch Package Manager"), _("Launch Package Manager"), self.launch_package_manager),
            ("web_panel", _("_Packages Website"), _("Use Packages web interface"), self.load_packages_url),
            ("web_site", _("_Sabayon Linux Website"), _("Launch Sabayon Linux Website"), self.load_website),
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

        self.status_icon = gtk.status_icon_new_from_pixbuf(self.icons.best_match("okay",22))
        self.status_icon.connect("popup-menu", self.applet_face_click)
        self.status_icon.connect("activate", self.applet_face_click2)

        hide_menu = False
        message = ''
        workdir_perms_issue = False
        if os.path.isdir(etpConst['entropyworkdir']):
            gid = os.stat(etpConst['entropyworkdir'])[5]
            if gid != etpConst['entropygid']:
                workdir_perms_issue = True

        permitted = entropyTools.is_user_in_entropy_group()
        load_intf = False
        if not permitted:
            hide_menu = True
            message = "%s: %s" % (_("You must add yourself to this group"),etpConst['sysgroup'],)
        elif workdir_perms_issue:
            hide_menu = True
            message = _("Please run Equo/Spritz as root to update Entropy permissions")
        else:
            load_intf = True

        if etp_applet_config.settings['APPLET_ENABLED']:
            self.enable_applet(init = True)
        else:
            self.disable_applet()

        if hide_menu:
            self.disable_refresh_timer()
            self.set_state("ERROR")
            self.update_tooltip(message)
            for key in self.menu_items:
                if key in ['exit','web_site','about','web_panel','update_now']:
                    continue
                w = self.menu_items[key]
                w.set_sensitive(False)
                w.hide()

        if load_intf:
            # Entropy initialization
            self.Entropy = Entropy(self)
            self.enable_refresh_timer()

    def task_queue_executor(self):
        while 1:
            try:
                data = self.TaskQueue.pop(0)
            except IndexError:
                return self.TaskQueueAlive
            func, args, kwargs = data
            if self.debug: print "queue_exec",func, args, kwargs
            func(*args,**kwargs)
            if not self.TaskQueueAlive:
                return False

    def set_menu_image(self, widget, name):
        img = gtk.Image()
        if name == "update_now":
            pix = self.icons.best_match("spritz",22)
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

    def enable_refresh_timer(self, when = etp_applet_config.settings['REFRESH_INTERVAL'] * 1000):
        if self.current_state in [ "CRITICAL" ]: return
        if not self.refresh_timeout_tag:
            self.refresh_timeout_tag = TimeScheduled(when/1000, self.refresh_handler)
            self.refresh_timeout_tag.set_delay_before(True)
            self.refresh_timeout_tag.start()

    def disable_refresh_timer(self):
        if self.refresh_timeout_tag:
            self.refresh_timeout_tag.kill()
            self.refresh_timeout_tag = None

    def start_working(self):
        self.isWorking = True

    def end_working(self):
        self.isWorking = False

    def change_icon(self, image):
        to_image = self.icons.best_match(image, self.applet_size)
        self.status_icon.set_from_pixbuf(to_image)

    def set_displayed_image(self, image):
        if isinstance(image,basestring): new_image = self.icons.best_match(image, self.applet_size)
        else: new_image = image
        self.current_image = new_image
        self.redraw()

    def redraw(self):
        if not self.current_image: return
        self.status_icon.set_from_pixbuf(self.current_image)
        self.status_icon.set_visible(True)

    def load_packages_url(self, *data):
        try:
            gnome.url_show("http://packages.sabayonlinux.org/")
        except gobject.GError:
            self.load_browser("http://packages.sabayonlinux.org/")

    def load_website(self, *data):
        try:
            gnome.url_show("http://www.sabayonlinux.org/")
        except gobject.GError:
            self.load_browser("http://www.sabayonlinux.org/")

    def load_browser(self, url):
        browser = None
        konq_ret = subprocess.call("which konqueror &> /dev/null", shell = True)
        if os.access("/usr/bin/firefox",os.X_OK):
            browser = "/usr/bin/firefox"
        elif konq_ret:
            browser = "konqueror"
        elif os.access("/usr/bin/opera",os.X_OK):
            browser = "/usr/bin/opera"
        if browser:
            subprocess.call([browser,url])

    def disable_applet(self, *args):
        self.update_tooltip(_("Updates Notification Applet Disabled"))
        self.disable_refresh_timer()
        self.set_state("DISABLE")
        etp_applet_config.settings['APPLET_ENABLED'] = 0
        etp_applet_config.save_settings(etp_applet_config.settings)
        self.menu_items['disable_applet'].hide()
        self.menu_items['enable_applet'].show()

    def enable_applet(self, init = False):
        self.update_tooltip(_("Updates Notification Applet Enabled"))
        if not init:
            self.enable_refresh_timer()
        self.set_state("OKAY")
        etp_applet_config.settings['APPLET_ENABLED'] = 1
        etp_applet_config.save_settings(etp_applet_config.settings)
        self.menu_items['disable_applet'].show()
        self.menu_items['enable_applet'].hide()

    def launch_package_manager(self, *data):

        def spawn_spritz():
            os.execv('/usr/bin/spritz', ['spritz'])

        t = ParallelTask(spawn_spritz)
        t.start()

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

    def compare_repositories_status(self):
        repos = {}

        try:
            repoConn = self.Entropy.Repositories(noEquoCheck = True, fetchSecurity = False)
        except MissingParameter:
            return repos,1 # no repositories specified
        except OnlineMirrorError:
            return repos,2 # not connected ??
        except Exception, e:
            return repos,str(e) # unknown error

        # now get remote
        for repoid in etpRepositories:
            if repoConn.is_repository_updatable(repoid):
                self.Entropy.repository_move_clear_cache(repoid)
                repos[repoid] = {}
                repos[repoid]['local_revision'] = self.Entropy.get_repository_revision(repoid)
                repos[repoid]['remote_revision'] = repoConn.get_online_repository_revision(repoid)

        del repoConn

        return repos, 0

    def refresh_handler(self, force = 0, after = 0):
        if after: time.sleep(after)
        self.refresh(force)

    def refresh(self, force = 0):

        if not self.Entropy:
            if self.debug: print "refresh: Entropy interface not loaded"
            return
        if not etp_applet_config.settings['APPLET_ENABLED']:
            if self.debug: print "refresh: applet not enabled"
            return
        if self.debug: print "refresh: all fine, getting lock and running run_refresh"

        self.refresh_lock.acquire()
        try:
            t = ParallelTask(self.run_refresh, force)
            t.start()
            while t.isAlive():
                self.status_icon.set_visible(True)
                self.task_queue_executor()
                time.sleep(0.3)
            return t.get_rc()
        finally:
            self.refresh_lock.release()


    def run_refresh(self, force):

        locked = self.Entropy.application_lock_check(silent = True)

        if self.debug: print "run_refresh: I am here"

        self.start_working()
        old_tip = self.tooltip_text
        old_state = self.current_state

        self.disable_network_timer()
        self.set_state("BUSY", use_busy_icon = force)
        self.update_tooltip(_("Checking for updates..."))

        self.last_error = None
        self.last_error_is_network_error = 0
        self.error_threshold = 0
        self.available_packages = []

        rc = 0
        if not locked:

            # compare repos
            if self.debug: print "run_refresh: launching compare_repositories_status"
            repositories_to_update, rc = self.compare_repositories_status()
            if self.debug: print "run_refresh: completed compare_repositories_status: %s" % ((repositories_to_update, rc),)

            if repositories_to_update and rc == 0:
                repos = repositories_to_update.keys()

                if self.debug: print "run_refresh: loading repository interface"
                try:
                    repoConn = self.Entropy.Repositories(repos, fetchSecurity = False, noEquoCheck = True)
                    if self.debug: print "run_refresh: repository interface loaded"
                except MissingParameter, e:
                    self.last_error = "%s: %s" % (_("No repositories specified in"),etpConst['repositoriesconf'],)
                    self.error_threshold += 1
                    if self.debug: print "run_refresh: MissingParameter exception, error: %s" % (e,)
                except OnlineMirrorError, e:
                    self.last_error = _("Repository Network Error")
                    self.last_error_is_network_error = 1
                    if self.debug: print "run_refresh: OnlineMirrorError exception, error: %s" % (e,)
                except Exception, e:
                    self.error_threshold += 1
                    self.last_error_is_exception = 1
                    self.last_error = "%s: %s" % (_('Unhandled exception'),e,)
                    if self.debug: print "run_refresh: Unhandled exception, error: %s" % (e,)
                else:
                    # -128: sync error, something bad happened
                    # -2: repositories not available (all)
                    # -1: not able to update all the repositories
                    if self.debug: print "run_refresh: preparing to run sync"
                    rc = repoConn.sync()
                    rc = rc*-1
                    del repoConn
                    if self.debug: print "run_refresh: sync done"
                if self.debug: print "run_refresh: sync closed, rc: %s" % (rc,)

            if rc == 1:
                err = _("No repositories specified. Cannot check for package updates.")
                self.show_alert( _("Updates: attention"), err )
                self.error_threshold += 1
                self.last_error = err
            elif rc == 2:
                err = _("Cannot connect to the Updates Service, you're probably not connected to the world.")
                self.show_alert( _("Updates: connection issues"), err )
                self.last_error_is_network_error = 1
                self.last_error = err
            elif rc == -1:
                err = _("Not all the repositories have been fetched for checking")
                self.show_alert( _("Updates: repository issues"), err )
                self.last_error_is_network_error = 1
                self.last_error = err
            elif rc == -2:
                err = _("No repositories found online")
                self.show_alert( _("Updates: repository issues"), err )
                self.last_error_is_network_error = 1
                self.last_error = err
            elif rc == -128:
                err = _("Synchronization errors. Cannot update repositories. Check logs.")
                self.show_alert( _("Updates: sync issues"), err )
                self.error_threshold += 1
                self.last_error = err
            elif isinstance(rc,basestring):
                self.show_alert( _("Updates: unhandled error"), rc )
                self.error_threshold += 1
                self.last_error_is_exception = 1
                self.last_error = rc

            if self.last_error_is_network_error:
                self.update_tooltip(_("Updates: connection issues"))
                self.set_state("DISCONNECTED")
                self.end_working()
                return False

        try:
            update, remove, fine = self.Entropy.calculate_world_updates()
            del fine, remove
        except Exception, e:
            msg = "%s: %s" % (_("Updates: error"),e,)
            self.show_alert(_("Updates: error"), msg)
            self.error_threshold += 1
            self.last_error_is_exception = 1
            self.last_error = str(e)

        if self.last_error:
            self.disable_refresh_timer()
            msg = "%s: %s" % (_("Updates issue:"),self.last_error,)
            self.update_tooltip(msg)
            self.set_state("ERROR")
            self.end_working()
            return False

        if rc == 0:
            self.update_tooltip(old_tip)

        if update:
            self.available_packages = update[:]
            self.set_state("CRITICAL")
            msg = "%s %d %s" % (_("There are"),len(update),_("updates available."),)
            self.update_tooltip(msg)
            self.show_alert(    _("Updates available"),
                                msg,
                                urgency = 'critical'
                        )
            if self.notice_window:
                self.refresh_notice_window()

        else:
            self.set_state(old_state)
            self.update_tooltip(_("So far, so good. w00t!"))
            self.show_alert(    _("Everything up-to-date"),
                                _("So far, so good. w00t!"),
                                urgency = 'low'
                        )

        self.end_working()
        return True

    def is_network_error(self, msg):
        if msg.find("SysCallError") >= 0 and msg.find("104") >= 0:
            return 1
        if msg.find("onnection") >= 0:
            return 1
        if msg.find("etwork") >= 0:
            return 1
        if msg.find("certificate verify failed") >= 0:
            return 0
        if msg.find("SSL") >= 0:
            return 1
        return 0

    def network_retry_handler(self, force):
        self.refresh(force)

    def enable_network_timer(self, when = etp_applet_config.settings['NETWORK_RETRY_INTERVAL'] * 1000, force = 0):
        if self.current_state != "DISCONNECTED": return
        if not self.network_timeout_tag:
            self.network_timeout_tag = TimeScheduled(when/1000, self.network_retry_handler, force = force)
            self.network_timeout_tag.set_delay_before(True)
            self.network_timeout_tag.start()

    def disable_network_timer(self):
        if self.network_timeout_tag:
            self.network_timeout_tag.kill()
            self.network_timeout_tag = None

    def update_tooltip(self, tip):
        self.tooltip_text = tip
        def _update_tooltip(tip):
            self.status_icon.set_tooltip(tip)
        if self.debug: print "queued:",_update_tooltip
        self.TaskQueue.append((_update_tooltip,[tip],{},))

    def update_from_server(self, widget=None):
        self.enable_applet()
        self.refresh(force = 1)

    def user_consented(self):
        self.consent = 1

    def notice_window_closed(self):
        self.notice_window = None

    def exit_applet(self, *args):

        entropyTools.kill_threads()
        self.TaskQueueAlive = False

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
        self.about_window = rhnAppletAboutWindow(self)

    def about_dialog_closed(self):
        self.about_window = None

    def rhnreg_dialog_closed(self):
        self.rhnreg_dialog = None

    def error_dialog_closed(self):
        self.error_dialog = None
        self.last_error = None
        self.last_error_is_exception = 0
        self.last_error_is_network_error = 0
        self.set_state("OKAY")
        self.update_tooltip(_("Waiting before checkin..."))
        self.enable_refresh_timer()

    def applet_face_click(self, icon, button, activate_time):

        if button == 3:
            self.menu.popup(None, None, None, 0, activate_time)
            return

    def applet_face_click2(self, icon):

        if not self.current_state in [ "OKAY", "ERROR", "DISCONNECTED", "CRITICAL" ]:
            return

        if self.last_error:
            if self.error_dialog:
                return
            if self.last_error_is_exception:
                self.error_dialog = rhnAppletExceptionDialog(self, self.last_error)
            else:
                self.error_dialog = rhnAppletErrorDialog(self, self.last_error)
            return

        self.never_viewed_notices = 0
        if self.notice_window and not self.rhnreg_dialog:
            self.notice_window.close_window()
            return

        if not self.notice_window:
            self.notice_window = rhnAppletNoticeWindow(self)

        self.refresh_notice_window()

        if self.rhnreg_dialog:
            self.rhnreg_dialog.set_transient(self.notice_window)
            self.rhnreg_dialog.raise_()

    def refresh_notice_window(self):
        self.notice_window.clear_window()

        if not self.available_packages:
            return

        names = {}
        entropy_data = {}
        for pkg in self.available_packages:
            dbconn = self.Entropy.open_repository(pkg[1])
            atom = dbconn.retrieveAtom(pkg[0])
            avail = dbconn.retrieveVersion(pkg[0])
            avail_rev = dbconn.retrieveRevision(pkg[0])
            key, slot = dbconn.retrieveKeySlot(pkg[0])
            installed_match = self.Entropy.clientDbconn.atomMatch(key, matchSlot = slot)

            if installed_match[0] != -1:
                installed = self.Entropy.clientDbconn.retrieveVersion(installed_match[0])
                installed_rev = self.Entropy.clientDbconn.retrieveRevision(installed_match[0])
            else:
                installed = _("Not installed")
            if key == "sys-apps/entropy":
                entropy_data['avail'] = avail+"~"+str(avail_rev)[:]
                entropy_data['installed'] = installed+"~"+str(installed_rev)

            names[atom] = {}
            names[atom]['installed'] = installed+"~"+str(installed_rev)
            names[atom]['avail'] = avail+"~"+str(avail_rev)


        ordered_names = names.keys()
        ordered_names.sort()
        for name in ordered_names:
            self.notice_window.add_package( name,
                                            names[name]['installed'],
                                            names[name]['avail']
                                          )

        critical_text = []
        if entropy_data.has_key("avail"):
            msg = "%s sys-apps/entropy <b>%s</b> %s, %s <b>%s</b>. %s." % (
                    _("Your system currently has"),
                    entropy_data['installed'],
                    _("installed"),
                    _("but the latest available version is"),
                    entropy_data['avail'],
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
