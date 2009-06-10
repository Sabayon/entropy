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
import gobject
import gtk.glade
gtk.glade.bindtextdomain('entropy', "/usr/share/locale")
import gtk
from entropy.const import etpConst
from entropy.i18n import _
from entropy.core import SystemSettings
SysSettings = SystemSettings()

class GladeWindow:

    def __init__(self, filename, window_name):
        self.filename = filename
        if not os.path.isfile(filename):
            self.filename = "/usr/lib/entropy/sulfur/applet/%s" % (filename,)
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
            "on_launch_sulfur_clicked" : self.on_sulfur,
            "on_close_clicked" : self.on_close,
            })

        message_label = gtk.Label()
        message_label.set_line_wrap(True)
        self.message_label = message_label

    def on_sulfur(self, button):
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

            vb = gtk.VBox()
            vb.add(self.message_label)
            tab_label = gtk.Label(_("Critical Information"))

            tab_label.show()
            self.message_label.show()
            vb.show()

            self.critical_tab = self.notebook.prepend_page(vb, tab_label)
            self.critical_tab_contents = vb

            if critical_active:
                self.notebook.set_current_page(
                    self.notebook.page_num(self.critical_tab_contents))

            self.set_critical_tab_text(text)

        else:

            self.set_critical_tab_text(text)

    def set_critical_tab_text(self, text):
        self.message_label.set_markup(text)

    def remove_critical(self):
        if not self.critical_tab_contents:
            return

        self.notebook.remove_page(
            self.notebook.page_num(self.critical_tab_contents))

    def fill(self, pkg_data):
        self.package_list_model.clear()
        for name, avail in pkg_data:
            self.package_list_model.append((name, avail,))


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

def growToParent(*args):
    return

class WrappingLabel(gtk.Label):
    def __init__(self, label=""):
        gtk.Label.__init__(self, label)
        self.set_line_wrap(gtk.TRUE)
        self.ignoreEvents = 0
        self.connect("size-allocate", growToParent)

class AppletIconPixbuf:

    def __init__(self):
        self.images = {}

    def add_file(self, name, filename):

        if not self.images.has_key(name):
            self.images[name] = []
        from sulfur.setup import const
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
