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

from .cellrenderers import CellButtonRenderer, CellRendererNoticeView, \
    NoticeCellButtonIDs

from rigo.utils import open_url
from rigo.ui.gtk3.models.noticeboardliststore import NoticeBoardListStore

from rigo.ui.gtk3.widgets.generictreeview import GenericTreeView


class NoticeBoardTreeView(GenericTreeView):

    VARIANT_SHOW = 0

    __gsignals__ = {
        # Show Notice
        "show-notice" : (GObject.SignalFlags.RUN_LAST,
                         None,
                         (GObject.TYPE_PYOBJECT,),
                         ),
        }

    def __init__(self, icons, icon_size):
        Gtk.TreeView.__init__(self)

        tr = CellRendererNoticeView(
            icons, NoticeBoardListStore.ICON_SIZE,
            self.create_pango_layout(""))
        tr.set_pixbuf_width(icon_size)

        show_notice = CellButtonRenderer(
            self, name=NoticeCellButtonIDs.SHOW)
        show_notice.set_markup_variants(
            {self.VARIANT_SHOW: _("Show"),})
        tr.button_pack_end(show_notice)

        GenericTreeView.__init__(
            self, self._row_activated_callback,
            self._button_activated_callback, tr)

        column = Gtk.TreeViewColumn("Notices", tr,
                                    notice=self.COL_ROW_DATA)

        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(350)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(column)

    def _row_activated_callback(self, path, rowref):
        open_url(rowref.link())

    def _button_activated_callback(self, btn, btn_id, notice, store, path):
        if isinstance(store, Gtk.TreeModelFilter):
            store = store.get_model()
        if btn_id == NoticeCellButtonIDs.SHOW:
            self.emit("show-notice", notice)
        return False
