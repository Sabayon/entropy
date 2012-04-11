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
from gi.repository import Gtk, GObject


class PreferencesListStore(Gtk.ListStore):

    # NoticeBoard object
    COL_TYPES = (GObject.TYPE_PYOBJECT,)

    ICON_SIZE = 48

    __gsignals__ = {
        "redraw-request"  : (GObject.SignalFlags.RUN_LAST,
                             None,
                             tuple(),
                             ),
    }

    def __init__(self):
        Gtk.ListStore.__init__(self)
        self.set_column_types(self.COL_TYPES)
        self.set_default_sort_func(self._sort, user_data=None)
        self.set_sort_column_id(-1, Gtk.SortType.ASCENDING)

    def _sort(self, model, iter1, iter2, user_data):
        conf_a = model.get_value(iter1, 0)
        conf_b = model.get_value(iter2, 0)
        return conf_a.priority() >= conf_b.priority()
