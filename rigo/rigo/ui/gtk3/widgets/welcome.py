# -*- coding: utf-8 -*-
"""
Copyright (C) 2012 Fabio Erculiani

Authors:
  Fabio Erculiani

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""
import os

from gi.repository import Gtk

from rigo.paths import DATA_DIR

from entropy.i18n import _


class WelcomeBox(Gtk.VBox):

    def __init__(self):
        Gtk.VBox.__init__(self)
        self._image_path = os.path.join(DATA_DIR, "ui/gtk3/art/rigo.png")

    def render(self):
        image = Gtk.Image.new_from_file(self._image_path)
        label = Gtk.Label()
        label.set_markup(_("<i>Browse <b>Applications</b> with ease</i>"))
        self.pack_start(image, False, False, 0)
        self.pack_start(label, False, False, 0)
        label.show()
        image.show()
