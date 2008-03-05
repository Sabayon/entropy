# This file is a portion of the Red Hat Network Panel Applet
#
# Copyright (C) 1999-2002 Red Hat, Inc. All Rights Reserved.
# Distributed under GPL version 2.
#
# Author: Chip Turner
#
# $Id: rhn_applet_dialogs.py,v 1.30 2003/10/14 17:41:34 veillard Exp $

from entropyConstants import *
from i18n import _
import gnome
import gnome.ui
import gobject
import gtk.glade
gtk.glade.bindtextdomain('spritz', "/usr/share/locale")
import gtk
import gtkhtml2

class rhnGladeWindow:
    def __init__(self, filename, window_name):
        self.filename = filename
        if not os.path.isfile(filename):
            self.filename = "/usr/share/entropy/spritz/applet/%s" % (filename,)
        self.xml = gtk.glade.XML(self.filename, window_name, domain="spritz")
        self.window = self.xml.get_widget(window_name)

    def get_widget(self, widget):
        return self.xml.get_widget(widget)

class rhnAppletNoticeWindow(rhnGladeWindow):
    def __init__(self, parent):
        rhnGladeWindow.__init__(self, "etp_applet.glade", "notice_window_2")

        self.parent = parent
        self.window.connect('delete_event', self.close_window)

        self.package_list = self.get_widget('update_clist')
        self.package_list.append_column(gtk.TreeViewColumn(_("Package Name"), gtk.CellRendererText(), text=0))
        self.package_list.append_column(gtk.TreeViewColumn(_("Version Installed"), gtk.CellRendererText(), text=1))
        self.package_list.append_column(gtk.TreeViewColumn(_("Available"), gtk.CellRendererText(), text=2))
        self.package_list.get_selection().set_mode(gtk.SELECTION_NONE)

        self.ignore_list = self.get_widget('ignore_clist')
        self.ignore_list.append_column(gtk.TreeViewColumn(_("Ignored Packages"), gtk.CellRendererText(), text=0))
        self.ignore_list.get_selection().set_mode(gtk.SELECTION_SINGLE)
        self.ignore_list_contents = []

        self.available_list = self.get_widget('available_clist')
        self.available_list.append_column(gtk.TreeViewColumn(_("Available Updates"), gtk.CellRendererText(), text=0))
        self.available_list.get_selection().set_mode(gtk.SELECTION_SINGLE)
        self.available_list_contents = []

        self.notebook = self.get_widget('notice_notebook')
        self.critical_tab = None
        self.critical_tab_contents = None

        self.available_model = gtk.ListStore(gobject.TYPE_STRING)
        self.available_list.set_model(self.available_model)

        self.ignore_list_model = gtk.ListStore(gobject.TYPE_STRING)
        self.ignore_list.set_model(self.ignore_list_model)

        self.package_list_model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.package_list.set_model(self.package_list_model)

        self.xml.signal_autoconnect (
            {
            "on_launch_up2date_clicked" : self.on_up2date,
            "on_ignore_clicked" : self.on_ignore_clicked,
            "on_unignore_clicked" : self.on_unignore_clicked,
            "on_close_clicked" : self.on_close,
            })

    def on_up2date(self, button):
        self.parent.launch_up2date()
        
    def on_close(self, close_button):
        self.close_window()

    def close_window(self, *rest):
        self.window.destroy()
        self.parent.notice_window_closed()

    def clear_window(self):

        self.available_model.clear()
        self.available_list_contents = []

        self.ignore_list_model.clear() 
        self.package_list_model.clear()
        self.ignore_list_contents = []

    def on_link_clicked(self, html, url):
        print "url: %s" % url
        
    def set_critical(self, text, critical_active):
        if not self.critical_tab_contents:
            html_view = gtkhtml2.View()
            self.html_view = html_view
            self.html_doc = gtkhtml2.Document()

            sw = gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            sw.set_border_width(2)
            sw.add(html_view)
            
            tab_label = gtk.Label(_("Critical Information"))
            tab_label.show()

            html_view.show()
            sw.show()

            self.critical_tab = self.notebook.prepend_page(sw, tab_label)
            self.critical_tab_contents = sw

            if critical_active:
                self.notebook.set_current_page(self.notebook.page_num(self.critical_tab_contents))
            
            self.set_critical_tab_text(text)
        else:
            if self.critical_tab_text != text:
                self.set_critical_tab_text(text)

    def set_critical_tab_text(self, text):
        self.critical_tab_text = text

        self.html_doc.clear()
        self.html_doc.connect('link_clicked', self.on_link_clicked)
        self.html_doc.open_stream("text/html")
        self.html_doc.write_stream('<meta http-equiv="Content-Type" content="text/html; charset=utf-8">' + text)
        self.html_doc.close_stream()
        self.html_view.set_document(self.html_doc)

    def remove_critical(self):
        if not self.critical_tab_contents:
            return

        self.notebook.remove_page(self.notebook.page_num(self.critical_tab_contents))

    def on_ignore_clicked(self, *data):
        selection = self.available_list.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return
        
        name = model.get_value(iter, 0)
        self.parent.set_ignored(name, 1)
    
    def on_unignore_clicked(self, *data):
        selection = self.ignore_list.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return
        
        name = model.get_value(iter, 0)
        self.parent.set_ignored(name, 0)
    
    def add_package(self, name, installed, avail):
        if self.parent.model.is_package_ignored(name):
            self.ignore_list_contents.append(name)
        else:
            self.available_list_contents.append(name)
            iter = self.package_list_model.append()
            self.package_list_model.set_value(iter, 0, name) 
            self.package_list_model.set_value(iter, 1, installed)
            self.package_list_model.set_value(iter, 2, avail)

    def redraw_lists(self):
        self.available_model.clear()

        self.available_list_contents.sort()
        for i in self.available_list_contents:
            iter = self.available_model.append()
            self.available_model.set_value(iter, 0, i) 

        self.ignore_list_model.clear()

        self.ignore_list_contents.sort()
        for i in self.ignore_list_contents:
            iter = self.ignore_list_model.append()
            self.ignore_list_model.set_value(iter, 0, i)

class rhnRegistrationPromptDialog(rhnGladeWindow):
    def __init__(self, parent):
        rhnGladeWindow.__init__(self, "etp_applet.glade", "need_to_register_dialog")
        
        self.parent = parent
        self.window.connect('delete_event', self.close_dialog)
        self.xml.signal_autoconnect (
            {
            "on_launch_rhnreg_clicked" : self.on_rhnreg,
            "on_close_clicked" : self.on_close,
            })

    def raise_(self):
        self.window.window.raise_()

    def set_transient(self, papa):
        self.window.set_transient_for(papa.window)
        
    def on_rhnreg(self, button):
        self.parent.launch_rhnreg()
        self.close_dialog()
        
    def close_dialog(self, *rest):
        self.window.destroy()
        self.parent.rhnreg_dialog_closed()

    def on_close(self, close_button):
        self.close_dialog()

class rhnAppletAboutWindow:
    def __init__(self, parent):
        self.window = gnome.ui.About("%s Updates Applet" % (etpConst['systemname'],),
                                     etpConst['entropyversion'], "Copyright (C) 2008, Sabayon Linux",
                                     "Sabayon Linux. What else?",
                                     [ "Sabayon Linux Team", "devel@sabayonlinux.org" ])
        self.window.connect("destroy", self.on_close)
        self.parent = parent
        self.window.show()

    def close_dialog(self, *rest):
        self.parent.about_dialog_closed()

    def on_close(self, *data):
        self.close_dialog()

class rhnAppletFirstTimeDruid(rhnGladeWindow):
    def __init__(self, parent, proxy_url, proxy_username, proxy_password):
        rhnGladeWindow.__init__(self, "etp_applet.glade", "first_time_druid")
        
        self.parent = parent
        self.window.connect('delete_event', self.close_dialog)
        self.xml.signal_autoconnect (
            {
            "on_cancel" : self.on_cancel,
            "on_remove_from_panel" : self.on_remove_from_panel,
            "on_finish" : self.on_finish,
            })

        color = gtk.gdk.color_parse("#cc0000")
        page = self.xml.get_widget("druidpagestart1")
        page.set_bg_color(color)
        page = self.xml.get_widget("druidpagefinish1")
        page.set_bg_color(color)

        html_sw = self.get_widget("tos_window")
        self.tos_document = gtkhtml2.Document()
        self.tos_view = gtkhtml2.View()
        html_sw.add(self.tos_view)
        self.tos_view.show()
        html_sw.show()
        self.tos_document.clear()
        self.tos_document.connect('link_clicked', self.on_link_clicked)
        self.tos_document.open_stream("text/html")

        # messy wordwrapping; helps i18n people though
        self.tos_document.write_stream(
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">' + 
            _("""Red Hat Network provides an intelligent, proactive management service for your Red Hat Linux-based system.  Red Hat Network has the latest Red Hat information, updates, and services to make your systems more secure and reliable.  This application is designed to inform you when updates are available for your system, but does not save any personally identifiable information about you or your system to the Red Hat Network unless you choose to subscribe to Red Hat Network. Use of this applet by itself does not imply any agreement with Red Hat Network.""") + "<br><br>" +
            _("""Use of the up2date service, or use of this applet in conjunction with the up2date service, is governed by the Red Hat Network Services Use and Subscription Agreement, which may be reviewed at """) +
            """<a href="https://rhn.redhat.com/help/terms.pxt">https://rhn.redhat.com/help/terms.pxt</a>.<br><br>""" +
            _("""Red Hat Network's privacy policy may be reviewed at """) +
            """<a href="https://rhn.redhat.com/help/security.pxt">https://rhn.redhat.com/help/security.pxt</a>.<br><br>""" +
            _("""If you do not wish to have this application appear on your panel, click the 'Remove From Panel' button below.  Once removed, you can return it to your panel at any time by clicking on the Red Fedora in the bottom left of the desktop, choosing 'System Tools' and then choosing 'Red Hat Network Alert Icon.'
            """))
        self.tos_document.close_stream()
        self.tos_view.set_document(self.tos_document)
                    
        
        self.enable_proxy = self.get_widget("enable_proxy_check")
        self.enable_proxy.connect("toggled", self.on_enable_proxy_toggle)

        self.enable_auth = self.get_widget("use_auth_check")
        self.enable_auth.connect("toggled", self.on_use_auth_toggle)

        self.proxy_entry = self.get_widget("proxy_entry")
        self.username_entry = self.get_widget("username_entry")
        self.password_entry = self.get_widget("password_entry")
        self.username_entry_label = self.get_widget("username_entry_label")
        self.password_entry_label = self.get_widget("password_entry_label")

        self.use_auth = 0
        self.use_proxy = 0

        self.proxy_entry.set_text(proxy_url)
        if proxy_url:
            self.use_proxy = 1
            self.enable_proxy.set_sensitive(gtk.TRUE)
            self.enable_proxy.activate()

            if proxy_username:
                self.use_auth = 1
                self.username_entry.set_text(proxy_username)
                self.password_entry.set_text(proxy_password)
                self.enable_auth.set_sensitive(gtk.TRUE)
                self.enable_auth.activate()
        self.window.show_all()

    def on_link_clicked(self, html, url):
        gnome.url_show(url)
        
    def on_enable_proxy_toggle(self, button):
        state = button.get_active()
        self.use_proxy = state

        self.get_widget("proxy_entry").set_sensitive(state)
        self.enable_auth.set_sensitive(state)

        if self.use_auth:
            self.username_entry.set_sensitive(state)
            self.username_entry_label.set_sensitive(state)
            self.password_entry.set_sensitive(state)
            self.password_entry_label.set_sensitive(state)
        
    def on_use_auth_toggle(self, button):
        state = button.get_active()
        self.use_auth = state

        self.username_entry.set_sensitive(state)
        self.username_entry_label.set_sensitive(state)
        self.password_entry.set_sensitive(state)
        self.password_entry_label.set_sensitive(state)
        
    def close_dialog(self, *data, **kwarg):
        if kwarg.has_key("remove"):
            self.parent.first_time_druid_closed(kwarg["remove"])
        else:
            self.parent.first_time_druid_closed(0)
        self.window.hide()

    def on_cancel(self, cancel_button):
        self.close_dialog(remove=0)

    def on_remove_from_panel(self, cancel_button):
        self.close_dialog(remove=1)

    def on_finish(self, *data):
        if self.use_proxy:
            args = [ self.proxy_entry.get_text() ]
            if self.use_auth:
                args.append(self.username_entry.get_text())
                args.append(self.password_entry.get_text())

            apply(self.parent.set_proxy, args)
                                  
        else:
            self.parent.set_proxy()
            
        self.parent.user_consented()
        self.close_dialog()

class rhnAppletErrorDialog(rhnGladeWindow):
    def __init__(self, parent, error):
        self.window = gtk.MessageDialog(None, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, str(error))
        self.window.set_modal(gtk.TRUE)
        self.window.connect("close", self.on_close)
        self.window.connect('response', self.on_close)
        self.parent = parent
        self.window.show()

    def close_dialog(self, *rest):
        self.parent.error_dialog_closed()
        self.window.destroy()

    def on_close(self, *data):
        self.close_dialog()
        
# stolen from anaconda
def growToParent(*args):
    return

def addFrame(dialog, title=None):
    contents = dialog.get_children()[0]
    dialog.remove(contents)
    frame = gtk.Frame()
    frame.set_shadow_type(gtk.SHADOW_OUT)
    box = gtk.VBox()
    try:
        if title is None:
            title = dialog.get_title()

        if title:
            data = {}
            data["state"] = 0
            data["button"] = 0
            data["deltax"] = 0
            data["deltay"] = 0
            data["window"] = dialog
            eventBox = gtk.EventBox()
            eventBox.connect("button-press-event", titleBarMousePressCB, data)
            eventBox.connect("button-release-event", titleBarMouseReleaseCB, data)
            eventBox.connect("motion-notify-event", titleBarMotionEventCB,data)
            titleBox = gtk.HBox(gtk.FALSE, 5)
            eventBox.add(titleBox)
            eventBox.modify_bg(gtk.STATE_NORMAL,
                               eventBox.rc_get_style().bg[gtk.STATE_SELECTED])
            titlelbl = gtk.Label("")
            titlelbl.set_markup("<b>"+_(title)+"</b>")
            titlelbl.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
            titlelbl.set_property("ypad", 4)
            titleBox.pack_start(titlelbl)
            box.pack_start(eventBox, gtk.FALSE, gtk.FALSE)
    except:
        pass

    frame2=gtk.Frame()
    frame2.set_shadow_type(gtk.SHADOW_NONE)
    frame2.set_border_width(4)
    frame2.add(contents)
    box.pack_start(frame2, gtk.TRUE, gtk.TRUE, padding=5)
    frame.add(box)
    frame.show()
    dialog.add(frame)

class WrappingLabel(gtk.Label):
    def __init__(self, label=""):
        gtk.Label.__init__(self, label)
        self.set_line_wrap(gtk.TRUE)
        self.ignoreEvents = 0
        self.connect("size-allocate", growToParent)

class rhnAppletExceptionDialog:
    def __init__ (self, parent, text):
        self.parent = parent
        win = gtk.Dialog("Exception Occured", None)
        self.window = win
        win.add_button('gtk-ok', 0)
        
        buffer = gtk.TextBuffer(None)
        buffer.set_text(text)
        textbox = gtk.TextView()
        textbox.set_buffer(buffer)
        textbox.set_property("editable", gtk.FALSE)
        textbox.set_property("cursor_visible", gtk.FALSE)
        sw = gtk.ScrolledWindow ()
        sw.add (textbox)
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        hbox = gtk.HBox (gtk.FALSE)
##         file = pixmap_file('gnome-warning.png')
##         if file:
##             hbox.pack_start (GnomePixmap (file), gtk.FALSE)

        info = WrappingLabel(_("An unhandled exception has occured.  This "
                               "is most likely a bug.  Please copy the "
                               "full text of this exception into an email "
                               "and send it to applet@rhn.redhat.com.  Thank you."))
        info.set_size_request (400, -1)

        hbox.pack_start (sw, gtk.TRUE)
        win.vbox.pack_start (info, gtk.FALSE)
        win.vbox.pack_start (hbox, gtk.TRUE)
        win.set_size_request (500, 300)
        win.set_position (gtk.WIN_POS_CENTER)
        addFrame(win)
        win.show_all()
        win.connect('close', self.on_close)
        win.connect('response', self.on_close)

    def close_dialog(self, *rest):
        self.parent.error_dialog_closed()
        self.window.destroy()

    def on_close(self, *data):
        self.close_dialog()
