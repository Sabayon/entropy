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

import os
import gnome
import gnome.ui
import gobject
import gtk.glade
gtk.glade.bindtextdomain('entropy', "/usr/share/locale")
import gtk
import gtkhtml2
from entropy.const import etpConst
from entropy.i18n import _
from entropy.core import SystemSettings
SysSettings = SystemSettings()

class GladeWindow:

    def __init__(self, filename, window_name):
        self.filename = filename
        if not os.path.isfile(filename):
            self.filename = "/usr/lib/entropy/spritz/applet/%s" % (filename,)
        self.xml = gtk.glade.XML(self.filename, window_name, domain="entropy")
        self.window = self.xml.get_widget(window_name)

    def get_widget(self, widget):
        return self.xml.get_widget(widget)

class AppletNoticeWindow(GladeWindow):

    def __init__(self, parent):
        GladeWindow.__init__(self, "etp_applet.glade", "notice_window_2")

        self.parent = parent
        self.window.connect('delete_event', self.close_window)

        self.package_list = self.get_widget('update_clist')
        self.package_list.append_column(
            gtk.TreeViewColumn(
                _("Application"), gtk.CellRendererText(), text=0))
        self.package_list.append_column(
            gtk.TreeViewColumn(_("Latest version"), gtk.CellRendererText(), text=1))
        self.package_list.get_selection().set_mode(gtk.SELECTION_NONE)

        self.notebook = self.get_widget('notice_notebook')
        self.critical_tab = None
        self.critical_tab_contents = None

        self.package_list_model = gtk.ListStore(gobject.TYPE_STRING,
            gobject.TYPE_STRING)
        self.package_list.set_model(self.package_list_model)

        self.xml.signal_autoconnect (
            {
            "on_launch_spritz_clicked" : self.on_spritz,
            "on_close_clicked" : self.on_close,
            })

    def on_spritz(self, button):
        self.parent.launch_package_manager()

    def on_close(self, close_button):
        self.close_window()

    def close_window(self, *rest):
        self.window.destroy()
        self.parent.notice_window_closed()

    def clear_window(self):
        self.package_list_model.clear()

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
                self.notebook.set_current_page(
                    self.notebook.page_num(self.critical_tab_contents))

            self.set_critical_tab_text(text)
        else:
            if self.critical_tab_text != text:
                self.set_critical_tab_text(text)

    def set_critical_tab_text(self, text):
        self.critical_tab_text = text

        self.html_doc.clear()
        self.html_doc.connect('link_clicked', self.on_link_clicked)
        self.html_doc.open_stream("text/html")
        self.html_doc.write_stream(
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">' + text)
        self.html_doc.close_stream()
        self.html_view.set_document(self.html_doc)

    def remove_critical(self):
        if not self.critical_tab_contents:
            return

        self.notebook.remove_page(
            self.notebook.page_num(self.critical_tab_contents))

    def fill(self, pkg_data):
        self.package_list_model.clear()
        for name, avail in pkg_data:
            self.package_list_model.append((name, avail,))


class AppletAboutWindow:

    def __init__(self, parent):
        self.window = gnome.ui.About("%s Updates Applet" % (
                SysSettings['system']['name'],
            ),
            etpConst['entropyversion'], "Copyright (C) 2009, Sabayon Linux",
            "Sabayon, what else?",
            [ "Sabayon Linux", "sabayon@sabayonlinux.org" ])
        self.window.connect("destroy", self.on_close)
        self.parent = parent
        self.window.show()

    def close_dialog(self, *rest):
        self.parent.about_dialog_closed()

    def on_close(self, *data):
        self.close_dialog()

class AppletErrorDialog(GladeWindow):
    def __init__(self, parent, error):
        GladeWindow.__init__(self)
        self.window = gtk.MessageDialog(None, 0,
            gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, str(error))
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

class AppletExceptionDialog:

    def __init__ (self, parent, text):
        self.parent = parent
        win = gtk.Dialog("Exception Occured", None)
        self.window = win
        win.add_button('gtk-ok', 0)

        mybuf = gtk.TextBuffer(None)
        mybuf.set_text(text)
        textbox = gtk.TextView()
        textbox.set_buffer(buffer)
        textbox.set_property("editable", gtk.FALSE)
        textbox.set_property("cursor_visible", gtk.FALSE)
        sw = gtk.ScrolledWindow ()
        sw.add (textbox)
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        hbox = gtk.HBox (gtk.FALSE)

        info = WrappingLabel(_("An unhandled exception has occured.  This "
                               "is most likely a bug.  Please copy the "
                               "full text of this exception into an email "
                               "and send it to sabayon@sabayonlinux.org.  Thank you."))
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

class AppletIconPixbuf:

    def __init__(self):
        self.images = {}

    def add_file(self, name, filename):

        if not self.images.has_key(name):
            self.images[name] = []
        from spritz_setup import const
        filepath = const.PIXMAPS_PATH + "/applet/" + filename
        if not os.path.isfile(filepath):
            filename = "../gfx/applet/" + filename
        else:
            filename = filepath

        if not os.access(filename, os.R_OK):
            raise Exception,"Cannot open image file %s" % filename

        pixbuf = gtk.gdk.pixbuf_new_from_file(filename)

        self.add(name, pixbuf)

    def add(self, name, pixbuf):
        self.images[name].append(pixbuf)

    def best_match(self, name, size):
        best = None

        for image in self.images[name]:
            if not best:
                best = image
                continue
            if abs(size - image.height) < abs(size - best.height):
                best = image

        return best
