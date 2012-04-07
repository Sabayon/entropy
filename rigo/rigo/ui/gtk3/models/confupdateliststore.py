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
from gi.repository import Gtk, GObject, GLib


class ConfigUpdatesListStore(Gtk.ListStore):

    # ConfigUpdate object
    COL_TYPES = (GObject.TYPE_PYOBJECT,)

    ICON_SIZE = 48

    __gsignals__ = {
        # Redraw signal, requesting UI update
        "redraw-request"  : (GObject.SignalFlags.RUN_LAST,
                             None,
                             tuple(),
                             ),
    }

    def __init__(self):
        Gtk.ListStore.__init__(self)
        self.set_column_types(self.COL_TYPES)

