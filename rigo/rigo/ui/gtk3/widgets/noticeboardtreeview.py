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
from gi.repository import Gtk

from cellrenderers import CellButtonRenderer, CellRendererNoticeView

from rigo.utils import open_url
from rigo.ui.gtk3.models.noticeboardliststore import NoticeBoardListStore

from rigo.ui.gtk3.widgets.generictreeview import GenericTreeView


class NoticeBoardTreeView(GenericTreeView):

    def __init__(self, icons, icon_size):
        Gtk.TreeView.__init__(self)

        tr = CellRendererNoticeView(
            icons, NoticeBoardListStore.ICON_SIZE,
            self.create_pango_layout(""))
        tr.set_pixbuf_width(icon_size)

        GenericTreeView.__init__(
            self, self._row_activated_callback, None, tr)

        column = Gtk.TreeViewColumn("Notices", tr,
                                    notice=self.COL_ROW_DATA)

        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(350)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(column)

    def _row_activated_callback(self, path, rowref):
        open_url(rowref.link())
