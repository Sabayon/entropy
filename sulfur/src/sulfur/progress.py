# -*- coding: utf-8 -*-
#    Sulfur (Entropy Interface)
#    Copyright: (C) 2007-2009 Fabio Erculiani < lxnay<AT>sabayonlinux<DOT>org >
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from entropy.const import const_convert_to_unicode
import gobject
import gtk
from sulfur.setup import cleanMarkupString

class Base:

    def __init__(self, ui, set_page_func, parent):
        self.ui = ui
        self.set_page_func = set_page_func
        self.parent = parent
        self.ui.progressMainLabel.set_text("")
        self.ui.progressSubLabel.set_text("")
        self.ui.progressExtraLabel.set_text("")
        self.ui.progressBar.set_fraction(0)
        self.ui.progressBar.set_text(" ")
        self.lastFrac = 0.0
        self.lastFracSync = 0.0

    def show(self):
        self.lastFracSync = 0.0
        def run():
            self.ui.progressBox.show()
            self.set_page_func('output')
            self.lastFrac = 0.0
            return False
        gobject.idle_add(run)

    def reset_progress(self):
        self.lastFracSync = 0.0
        def run():
            self.lastFrac = 0.0
            self.ui.progressBar.set_fraction(0)
            self.ui.progressBar.set_text(" ")
            return False
        gobject.idle_add(run)

    def hide(self, clean=False):
        self.lastFracSync = 0.0
        def run():
            self.ui.progressBox.hide()
            if clean:
                self.ui.progressMainLabel.set_text("")
                self.ui.progressSubLabel.set_text("")
                self.ui.progressExtraLabel.set_text("")
                self.ui.progressBar.set_fraction(0)
                self.ui.progressBar.set_text(" ")
                self.lastFrac = 0.0
            return False
        gobject.idle_add(run)

    def set_progress(self, frac, text=None):
        self.lastFracSync = frac
        def run(frac, text):
            if frac == self.lastFrac:
                return
            self.lastFrac = frac
            if frac > 1 or frac < 0.0:
                return
            if frac >= 0 and frac <= 1:
                self.ui.progressBar.set_fraction(frac)
            else:
                self.ui.progressBar.set_fraction(0)

            if text is not None:
                self.ui.progressBar.set_text(text)

        gobject.idle_add(run, frac, text)

    def set_text(self, text):
        def run(text):
            self.ui.progressBar.set_text(text)
            return False
        gobject.idle_add(run, text)

    def set_mainLabel(self, text):
        def run(text):
            self.ui.progressMainLabel.set_markup("<b>%s</b>" % (text,))
            self.ui.progressSubLabel.set_text("")
            self.ui.progressExtraLabel.set_text("")
            return False
        gobject.idle_add(run, text)

    def set_subLabel(self, text):
        def run(text):
            mytxt = const_convert_to_unicode(text)
            if len(mytxt) > 80:
                mytxt = mytxt[:80].strip()+"..."
            self.ui.progressSubLabel.set_markup("%s" % (cleanMarkupString(mytxt),))
            self.ui.progressExtraLabel.set_text("")
            return False
        gobject.idle_add(run, text)

    def set_extraLabel(self, text):
        def run(text):
            mytxt = const_convert_to_unicode(text)
            if len(mytxt) > 80:
                mytxt = mytxt[:80].strip()+"..."
            self.ui.progressExtraLabel.set_markup(
                "<span size=\"small\">%s</span>" % cleanMarkupString(mytxt))
            return False
        gobject.idle_add(run, text)

    def gtk_loop(self):
        while gtk.events_pending():
           gtk.main_iteration()
