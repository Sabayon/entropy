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

from .cellrenderers import CellButtonRenderer, CellRendererGroupView, \
    GroupCellButtonIDs

from rigo.ui.gtk3.models.groupliststore import GroupListStore

from rigo.ui.gtk3.widgets.generictreeview import GenericTreeView

from entropy.i18n import _

class GroupTreeView(GenericTreeView):

    VARIANT_VIEW = 0

    def __init__(self, icons, icon_size):
        Gtk.TreeView.__init__(self)

        tr = CellRendererGroupView(
            icons, GroupListStore.ICON_SIZE,
            self.create_pango_layout(""))
        tr.set_pixbuf_width(icon_size)

        # create buttons and set initial strings
        v_button = CellButtonRenderer(
            self, name=GroupCellButtonIDs.VIEW)
        v_button.set_markup_variants(
            {self.VARIANT_VIEW: _("View")})
        tr.button_pack_end(v_button)

        GenericTreeView.__init__(
            self, self._row_activated_callback,
            self._button_activated_callback, tr)

        column = Gtk.TreeViewColumn("Groups", tr,
                                    group=self.COL_ROW_DATA)

        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(350)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_reorderable(False)
        column.set_sort_column_id(-1)
        self.append_column(column)

    def _row_activated_callback(self, path, rowref):
        rowref.run()

    def _button_activated_callback(self, btn, btn_id, cu, store, path):
        if isinstance(store, Gtk.TreeModelFilter):
            store = store.get_model()

        if btn_id == GroupCellButtonIDs.VIEW:
            rowref = self.get_rowref(store, path)
            return rowref.run()
        return False
