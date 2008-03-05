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

import gnome
import gnome.ui
# from msw to avoid odd bugs in some pygtk builds
try:
    from gtk import _disable_gdk_threading
    _disable_gdk_threading()
except ImportError:
    pass
import gtk
import gobject
import gtk.gdk
import egg.trayicon
import pynotify

import subprocess
import os
import sys
import math
import traceback
import time
import threading

import etp_applet_animation
from etp_applet_dialogs import \
     rhnAppletNoticeWindow, \
     rhnRegistrationPromptDialog, \
     rhnAppletAboutWindow, \
     rhnAppletFirstTimeDruid, \
     rhnAppletErrorDialog, \
     rhnAppletExceptionDialog
import etp_applet_config
from i18n import _

# Entropy imports
from entropyConstants import *
import exceptionTools
from entropy import EquoInterface,RepoInterface,urlFetcher

class Entropy(EquoInterface):

    def __init__(self):
        EquoInterface.__init__(self, noclientdb = True, indexing = False, user_xcache = True) #, xcache = False)
        self.xcache = True
        self.clientDbconn.xcache = True
        self.nocolor()

    def connect_progress_objects(self, tooltip_widget, tooltip_function):
        self.progress_tooltip = tooltip_function
        self.progress_widget = tooltip_widget
        self.updateProgress = self.appletUpdateProgress
        self.progress_tooltip_message_title = _("Updates Notification")
        self.appletCreateNotification()
        self.progress_tooltip_notification_timer = None
        self.applet_notification_active = 0
        gobject.timeout_add(5000, self.appletRemoveNotification)
        self.urlFetcher = GuiUrlFetcher
        self.progress = self.appletPrintText # for the GuiUrlFetcher

    def appletCreateNotification(self):
        pynotify.init("Message Replace")
        self.progress_tooltip_notification = pynotify.Notification(self.progress_tooltip_message_title,"Hello world")
        self.progress_tooltip_notification.set_timeout(0)

    def appletUpdateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):

        count_str = ""
        if count:
            if percent:
                count_str = str(int(round((float(count[0])/count[1])*100,1)))+"% "
            else:
                count_str = "(%s/%s) " % (str(count[0]),str(count[1]),)

        message = count_str+_(text)
        self.appletPrintText(message)

    def appletPrintText(self, message):
        self.progress_tooltip_notification.update(self.progress_tooltip_message_title,message)
        self.progress_tooltip_notification.show()
        self.applet_notification_active = 2

    def appletRemoveNotification(self):
        #self.appletInitTimer()
        if self.applet_notification_active == 0:
            return
        elif self.applet_notification_active == 2:
            self.applet_notification_active = 1
            return

        self.progress_tooltip_notification.set_timeout(1)
        time.sleep(1.5)
        self.applet_notification_active = 0
        self.appletCreateNotification()

class GuiUrlFetcher(urlFetcher):

    def connect_to_gui(self, progress):
        self.progress = progress

    def updateProgress(self):
        self.gather = self.downloadedsize
        message = "Fetching data %s/%s kB @ %s" % (
                                        str(round(float(self.downloadedsize)/1024,1)),
                                        str(round(self.remotesize,1)),
                                        str(self.entropyTools.bytesIntoHuman(self.datatransfer))+"/sec",
                                    )
        self.progress(message)

class rhnApplet:
    def set_state(self, new_state, use_busy_icon = 0):
        if not new_state in etp_applet_config.APPLET_STATES:
            raise "Error: invalid state %s" % new_state

        if self.current_state and not new_state in etp_applet_config.APPLET_STATE_CHANGES[self.current_state]:
            raise "Error: can't change from state %s to state %s" % (self.current_state, new_state)

        if self.refresh_timeout_tag and new_state not in [ "OKAY", "CRITICAL" ]:
            raise "Error: can't switch to state %s while refresh timer is on" % new_state

        if new_state == "OKAY":
            self.animate_to("okay")
        elif new_state == "BUSY":
            if use_busy_icon:
                self.set_displayed_image("busy")
        elif new_state == "CRITICAL":
            if self.never_viewed_notices:
                self.animate_to("critical", "critical-blank")
            else:
                self.set_displayed_image("critical")
        elif new_state == "NOCONSENT":
            if self.never_viewed_consent:
                self.animate_to("noconsent", "noconsent-blank")
            else:
                self.set_displayed_image("noconsent")
        elif new_state == "DISCONNECTED":
            self.animate_to("disconnect")
        elif new_state == "ERROR":
            self.animate_to("error")

        self.current_state = new_state


    def __init__(self):

        # this must be done before !!
        self.Entropy = Entropy()
        self.move_to_user_directory()
        self.Entropy.validate_repositories_cache()

        self.destroyed = 0
        self.tooltip_text = ""
        gnome.program_init("spritz-updater", etpConst['entropyversion'])
        self.tooltip = gtk.Tooltips()
        self.applet_window = egg.trayicon.TrayIcon("spritz-updater")
        self.applet_window.connect("destroy", self.exit_applet)
        self.Entropy.connect_progress_objects(self.tooltip, self.update_tooltip)

        #
        # Cope with a change in the Gnome python bindings naming
        #
        try:
            self.session = gnome.ui.gnome_master_client()
        except:
            self.session = gnome.ui.master_client()
        if self.session:
            gtk.Object.connect(self.session, "save-yourself",
                                self.save_yourself)
            gtk.Object.connect(self.session, "die", self.exit_applet)

        self.consent = {}
        self.never_viewed_consent = 1
        self.never_viewed_notices = 1

        self.current_image = None
        self.refresh_timeout_tag = None
        self.animate_timeout_tag = None
        self.current_state = None
        self.old_critical_text = None
        self.network_timeout_tag = None

        self.icons = etp_applet_animation.rhnAppletIconPixbuf()

        self.icons.add_file("okay", "applet-okay.png")
        self.icons.add_file("error", "applet-error.png")
        self.icons.add_file("busy", "applet-busy.png")
        self.icons.add_file("critical", "applet-critical.png")
        self.icons.add_file("critical-blank", "applet-critical-blank.png")
        self.icons.add_file("noconsent", "applet-critical.png")
        self.icons.add_file("noconsent-blank", "applet-critical-blank.png")
        self.icons.add_file("disconnect", "applet-disconnect.png")
        self.icons.add_file("spritz","spritz.png")
        self.icons.add_file("about","applet-about.png")
        self.icons.add_file("web","applet-web.png")
        self.icons.add_file("configuration","applet-configuration.png")
        self.applet_size = 22

        menu_items = (
            ("check_now", _("_Check for updates"), _("Check for updates"), self.update_from_server),
            ("update_now", _("_Launch Package Manager"), _("Launch Package Manager"), self.launch_package_manager),
            #("configure_applet", _("C_onfiguration"), _("Configuration"), self.run_first_time_druid),
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

        self.event_box = gtk.EventBox()
        self.image_widget = gtk.Image()
        self.event_box.add(self.image_widget)
        self.event_box.set_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.CONFIGURE)

        self.image_widget.show()
        self.event_box.connect("button_press_event", self.applet_face_click)
        self.image_widget.connect('destroy', self.on_destroy)

        self.applet_window.add(self.event_box)
        self.applet_window.show_all()

        self.proxy = {}
        self.proxy_username = {}
        self.proxy_password = {}

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

        # first refresh should be 2 minutes after execution; this
        # should give the rest of the user's desktop environment time
        # to load, etc, and avoid competing with nautilus or whatever
        # else is loading.  subsequent intervals will be much larger.
        self.set_state("OKAY")
        self.update_tooltip(_("Waiting until first checkin..."))
        self.enable_refresh_timer(60000)

    def get_tray_coordinates(self):
        """
        get the trayicon coordinates to send to
        notification-daemon
        trayicon=egg.trayicon.TrayIcon
        return : [x,y]
        """
        trayicon = self.applet_window
        coordinates = trayicon.window.get_origin()
        size = trayicon.window.get_size()
        screen = trayicon.window.get_screen()
        screen_height = screen.get_height()
        if coordinates[1] <= screen_height/2:
            y=coordinates[1]+size[1]/2
        else:
            y=coordinates[1]-size[1]/2
        msg_xy=[coordinates[0],y]
        return tuple(msg_xy)

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
        else:
            pix = self.icons.best_match("busy",22)

        img.set_from_pixbuf(pix)
        widget.set_image(img)

    def enable_refresh_timer(self, when = etp_applet_config.settings['REFRESH_INTERVAL'] * 1000, force = 0):
        if self.current_state not in [ "OKAY", "CRITICAL" ]:
            raise "Can't enable timer unless in OKAY or CRITICAL state"
        if not self.refresh_timeout_tag:
            self.refresh_timeout_tag = gobject.timeout_add(when, self.refresh_handler, force)

    def disable_refresh_timer(self):
        if self.refresh_timeout_tag:
            gobject.source_remove(self.refresh_timeout_tag)
            self.refresh_timeout_tag = None

    def handle_gtk_events(self):
        while gtk.events_pending():
            gtk.main_iteration(False)

    def refresh_callback(self):
        self.handle_gtk_events()

    def on_do_draw(self, *data):
        self.redraw()

    def on_bg_change(self, *data):
        self.redraw()

    def on_size_allocate(self, *data):
        self.redraw()

    def on_configure(self, widget, event):
        if event.type == gtk.gdk.CONFIGURE:
            self.redraw()

    def animate_stop(self):
        self.disable_animation_timer()

        # not animating?  then our current image is correct
        if self.animator:
            self.set_displayed_image(self.animator.final_frame)
            self.animator = None

        self.redraw()

    def disable_animation_timer(self):
        if self.animate_timeout_tag:
            gobject.source_remove(self.animate_timeout_tag)
            self.animate_timeout_tag = None

    def animate_handler(self, *data):
        next_frame = self.animator.next_frame()
        if not next_frame:
            self.disable_animation_timer()
            return False

        self.current_image = next_frame
        self.redraw()

        return True

    def animate_to(self, image, cycle_image = None):

        # logic: one way animation?  then we skip this if we're asked
        # to animate to the same, and let it finish.  if it's a cycle,
        # and the start and end images are the same, then we also just
        # continue

        if self.current_image == image:
            if cycle_image:
                if self.animation_cycle == cycle_image:
                    return
            else:
                return

        if self.current_image:
            from_image = self.current_image.copy()
        else:
            from_image = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, 1, 8, self.applet_size, self.applet_size)
            from_image.fill(0)

        to_image = self.icons.best_match(image, self.applet_size)

        frames = etp_applet_animation.alpha_tween(from_image, to_image, 16)

        self.animator = etp_applet_animation.rhnAppletAnimation()

        # if we're already in the to_image state, let's just start cycling
        if self.current_image != to_image or cycle_image:
            self.animator.append_frames(frames)

        if cycle_image:
            cycle_frames = []

            to_image = self.icons.best_match(image, self.applet_size)
            from_image = self.icons.best_match(cycle_image, self.applet_size)
            cycle_frames = etp_applet_animation.alpha_tween(to_image, from_image, 16)

            self.animator.append_cycle(cycle_frames)

        if not self.animate_timeout_tag:
            self.animate_timeout_tag = gobject.timeout_add(int(math.floor(1000 * etp_applet_config.settings['ANIMATION_TOTAL_TIME']/len(frames))), self.animate_handler)

        self.animate_handler()

    def set_displayed_image(self, image):
        if type(image) == type(""):
            new_image = self.icons.best_match(image, self.applet_size)
        else:
            new_image = image

        self.disable_animation_timer()

        self.current_image = new_image
        self.redraw()

    def redraw(self):
        if not self.current_image:
            return

        self.image_widget.set_from_pixbuf(self.current_image)

    def on_destroy(self, *data):
        self.destroyed = 1
        self.disable_refresh_timer()
        self.disable_animation_timer()

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

    def launch_package_manager(self, *data):
        pid = os.fork()
        if not pid:
            pid2 = os.fork()
            if not pid2:
                os.execv('/usr/bin/spritz', ['spritz'])
                os.perror(_("execv didn't execv?"))
            else:
                os._exit(-1)

    def show_alert(self, title, text):
        pynotify.init("XY")
        n = pynotify.Notification(title, text)
        x,y = self.get_tray_coordinates()
        n.set_hint("x", x+11)
        n.set_hint("y", y+5)
        n.show()

    def move_to_user_directory(self):
        etpConst['dumpstoragedir'] = etp_applet_config.settings['CACHES_DIR']
        for repoid in etpRepositories:
            etpRepositories[repoid]['dbpath'] = etp_applet_config.settings['REPOS_DIR'] + "/" + repoid+ "/" + etpConst['product'] + "/" + etpConst['currentarch']
            if not os.path.isdir(etpRepositories[repoid]['dbpath']):
                os.makedirs(etpRepositories[repoid]['dbpath'])
            self.Entropy.update_repository_revision(repoid)

    def compare_repositories_status(self):
        repos = {}
        try:
            repoConn = RepoInterface(self.Entropy, list(etpRepositories), noEquoCheck = True)
        except exceptionTools.MissingParameter:
            return repos,1 # no repositories specified
        except exceptionTools.OnlineMirrorError:
            return repos,2 # not connected ??
        except Exception, e:
            return repos,str(e) # unknown error
        # now get remote
        for repoid in etpRepositories:
            if repoConn.is_repository_updatable(repoid):
                repos[repoid] = {}
                repos[repoid]['local_revision'] = self.Entropy.get_repository_revision(repoid)
                repos[repoid]['remote_revision'] = repoConn.get_online_repository_revision(repoid)

        return repos, 0

    # every N seconds we poke the model to see if anything has
    # changed.  changes can be new package lists from the server, the
    # rpmdb being updated, etc.  the model caches aggressively, so
    # this isn't expensive.  this is done asynchronous to all GUI
    # updates, to try to avoid stalling the UI
    def refresh_handler(self, force = 0):
        self.refresh(force)

    def refresh(self, force=0):

        old_tip = self.tooltip_text
        old_state = self.current_state

        self.disable_refresh_timer()
        self.disable_network_timer()

        self.set_state("BUSY", use_busy_icon = force)
        self.update_tooltip(_("Checking for updates..."))
        self.handle_gtk_events()
        self.last_error = None
        self.last_error_is_network_error = 0
        self.error_threshold = 0

        # compare repos
        repositories_to_update, rc = self.compare_repositories_status()
        if repositories_to_update and rc == 0:
            repos = repositories_to_update.keys()

            oldxcache = self.Entropy.xcache
            self.Entropy.xcache = False # to disable cache generation by RepoInterface
            try:
                repoConn = self.Entropy.Repositories(repos, fetchSecurity = False, noEquoCheck = True)
            except exceptionTools.MissingParameter:
                self.last_error = _("No repositories specified in %s") % (etpConst['repositoriesconf'],)
                self.error_threshold += 1
            except exceptionTools.OnlineMirrorError:
                self.last_error = _("Repository Network Error")
                self.last_error_is_network_error = 1
            except Exception, e:
                self.error_threshold += 1
                self.last_error_is_exception = 1
                self.last_error = _("Unhandled exception: %s" % (str(e),))
            else:
                # -128: sync error, something bad happened
                # -2: repositories not available (all)
                # -1: not able to update all the repositories
                rc = repoConn.sync()
                rc = rc*-1
                print "RETURNED",rc
            self.Entropy.xcache = oldxcache

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
        elif type(rc) is str:
            self.show_alert( _("Updates: unhandled error"), rc )
            self.error_threshold += 1
            self.last_error_is_exception = 1
            self.last_error = rc

        if self.last_error_is_network_error:
            self.update_tooltip(_("Updates: connection issues"))
            self.set_state("DISCONNECTED")
            self.disable_refresh_timer()
            self.enable_network_timer()
            return False


        print "NOW I SHOULD CHECK"
        try:
            update, remove, fine = self.Entropy.calculate_world_updates()
            del fine, remove
        except Exception, e:
            self.show_alert( _("Updates: exception %s") % (str(Exception),), str(e) )
            self.error_threshold += 1
            self.last_error_is_exception = 1
            self.last_error = str(e)

        if self.last_error:
            self.disable_refresh_timer()
            self.update_tooltip(_("Updates: issue: %s") % (str(self.last_error),))
            self.set_state("ERROR")
            return False

        if rc == 0:
            self.update_tooltip(old_tip)

        # it is possible that the applet was destroyed during the time it
        # took to update the model.  If the applet is gone, bail now.
        if self.destroyed:
            return False

        if update:
            self.set_state("CRITICAL")
            self.update_tooltip(_("There are %d updates available.") % (len(update),))
            if self.notice_window:
                self.refresh_notice_window(update)

        else:
            self.set_state(old_state)
            self.update_tooltip(_("So far, so good. w00t!"))

        self.disable_refresh_timer()
        self.enable_refresh_timer()
        return True

    #
    # Detection and handling of network related errors, the
    # server may be unreachable, or refusing connections, quite
    # common in case of laptops. If such an error is detected
    # the applet will try to retry the connections after a timeout
    # of etp_applet_config.settings['NETWORK_RETRY_INTERVAL'] seconds (one minute)
    # until it suceeeds reaching the server and then exit the
    # DISCONNECTED state
    #
    def is_network_error(self, msg):
        # print "is_network_error: '%s'" % (msg)
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
        if self.current_state != "DISCONNECTED":
            raise "Can't enable network timer unless in DISCONNECTED state"
        if not self.network_timeout_tag:
            self.network_timeout_tag = gobject.timeout_add(when, self.network_retry_handler, force)

    def disable_network_timer(self):
        if self.network_timeout_tag:
            gobject.source_remove(self.network_timeout_tag)
            self.network_timeout_tag = None

    def update_tooltip(self, tip):
        self.tooltip_text = tip
        self.tooltip.set_tip(self.applet_window, tip)

    def update_from_server(self, widget=None):
        self.refresh(force = 1)

    def user_consented(self):
        self.consent = 1

    def notice_window_closed(self):
        self.notice_window = None
        #ignored_package_str = "|".join(self.model.ignored_package_list())

    def help (self, args):
        gnome.help.goto ("file:///usr/share/doc/rhn-applet-@VERSION@/index.html")


    def exit_applet(*args):
        gtk.main_quit()
        return

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

    def applet_face_click(self, window, event, *data):
        if event.button == 3:
            self.menu.popup(None, None, None, 0, event.time)
            return

        if self.current_state in [ "CRITICAL", "NOCONSENT" ]:
            self.animate_stop()

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

        # clicked the face while it was loaded, and not while telling
        # them to register?  well, let's close it

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

    def refresh_notice_window(self, needed_packages = None):
        self.notice_window.clear_window()

        if not needed_package:
            print "no updates to show"
            return

        print "refresh notice window"
        return

        names = {}
        for pkg in needed_packages:
            if not names.has_key(pkg["name"]):
                names[pkg["name"]] = []

            names[pkg["name"]].append(pkg)

        ordered_names = names.keys()
        ordered_names.sort();

        for name in ordered_names:

            available = ', '.join(map(lambda p: p["nevr"], names[name]))
            # drop the ending ':' if there is no epoch
            if len(available) >= 1 and available[-1] == ":":
                available = available[:-1]


            #installed = self.model.installed_package(name)
            installed['name'] = "asdads"
            installed['version'] = "1.2.3"
            installed['release'] = "0"
            self.notice_window.add_package(name,
                                           "-".join((installed["name"],
                                                        installed["version"],
                                                        installed["release"])),
                                           available)

        critical_text = []

        # XXX show equo updates
        '''
        for a in self.model.alerts():
            if a.is_up2date_alert():
                current, latest = a.alert_data()
                critical_text.append(_("""
Your system currently has <b>%s</b> installed, but the latest
available version is <b>%s</b>.  It is recommended that you <b>upgrade
to the latest up2date</b> before updating any other packages.
""") % (self.model.pkg_as_nvr(current), self.model.pkg_as_nvr(latest)))
        '''

        if critical_text:
            if self.old_critical_text != critical_text:
                self.notice_window.set_critical('<br><br>'.join(critical_text), critical_active = 1)
            else:
                self.notice_window.set_critical('<br><br>'.join(critical_text), critical_active = 0)
            self.old_critical_text = critical_text
        else:
            self.notice_window.remove_critical()

        self.notice_window.redraw_lists()

    def set_ignored(self, name, new_value):
        self.never_viewed_notices = 0

        '''
        if self.model.is_package_ignored(name) and not new_value:
            self.model.remove_ignored_package(name)

        if not self.model.is_package_ignored(name) and new_value:
            self.model.add_ignored_package(name)

        needed_packages, ignored_needed_packages = self.model.needed_packages()
        self.system_needs_packages(needed_packages, ignored_needed_packages)
        '''

    def run(self):
        gtk.main()
