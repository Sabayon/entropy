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
from gi.repository import Gtk, Gdk, GObject, Pango
import os
from threading import Lock

from entropy.i18n import _

from .cellrenderers import CellButtonRenderer, \
    CellRendererConfigUpdateView, ConfigUpdateCellButtonIDs

from rigo.em import em, StockEms, Ems
from rigo.ui.gtk3.models.confupdateliststore import ConfigUpdatesListStore

from rigo.ui.gtk3.widgets.generictreeview import GenericTreeView


class ConfigUpdatesTreeView(GenericTreeView):

    __gsignals__ = {
        # Source configuration file edit signal
        "source-edit" : (GObject.SignalFlags.RUN_LAST,
                         None,
                         (GObject.TYPE_PYOBJECT,
                          GObject.TYPE_PYOBJECT),
                         ),
        # Show diff signal
        "show-diff" : (GObject.SignalFlags.RUN_LAST,
                       None,
                       (GObject.TYPE_PYOBJECT,
                        GObject.TYPE_PYOBJECT),
                       ),
        # Merge source configuration file signal
        "source-merge" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          (GObject.TYPE_PYOBJECT,
                           GObject.TYPE_PYOBJECT),
                          ),
        # Discard source configuration file signal
        "source-discard" : (GObject.SignalFlags.RUN_LAST,
                            None,
                            (GObject.TYPE_PYOBJECT,
                             GObject.TYPE_PYOBJECT),
                            ),
    }

    VARIANT_EDIT = 0
    VARIANT_DIFF = 2
    VARIANT_MERGE = 3
    VARIANT_DISCARD = 4

    def __init__(self, icons, icon_size):
        Gtk.TreeView.__init__(self)

        tr = CellRendererConfigUpdateView(
            icons, ConfigUpdatesListStore.ICON_SIZE,
            self.create_pango_layout(""))
        tr.set_pixbuf_width(icon_size)
        tr.set_button_spacing(em(0.3))

        # create buttons and set initial strings
        edit_source = CellButtonRenderer(
            self, name=ConfigUpdateCellButtonIDs.EDIT)
        edit_source.set_markup_variants(
                    {self.VARIANT_EDIT: _("Edit")})
        tr.button_pack_start(edit_source)

        edit_dest = CellButtonRenderer(
            self, name=ConfigUpdateCellButtonIDs.DIFF)
        edit_dest.set_markup_variants(
                    {self.VARIANT_DIFF: _("Difference")})
        tr.button_pack_start(edit_dest)

        merge = CellButtonRenderer(
            self, name=ConfigUpdateCellButtonIDs.MERGE)
        merge.set_markup_variants(
            {self.VARIANT_MERGE: _("Accept")})
        tr.button_pack_end(merge)

        discard = CellButtonRenderer(
            self, name=ConfigUpdateCellButtonIDs.DISCARD)
        discard.set_markup_variants(
            {self.VARIANT_DISCARD: _("Discard")})
        tr.button_pack_end(discard)

        GenericTreeView.__init__(self,
            self._row_activated_callback,
            self._button_activated_callback, tr)

        column = Gtk.TreeViewColumn("ConfigUpdates", tr,
                                    confupdate=self.COL_ROW_DATA)

        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(350)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(column)

    def _row_activated_callback(self, path, rowref):
        self.emit("source-edit", path, rowref)

    def _button_activated_callback(self, btn, btn_id, cu, store, path):
        if isinstance(store, Gtk.TreeModelFilter):
            store = store.get_model()
        if btn_id == ConfigUpdateCellButtonIDs.EDIT:
            self.emit("source-edit", path, cu)
        elif btn_id == ConfigUpdateCellButtonIDs.DIFF:
            self.emit("show-diff", path, cu)
        elif btn_id == ConfigUpdateCellButtonIDs.MERGE:
            self.emit("source-merge", path, cu)
            self.expanded_path = None
        elif btn_id == ConfigUpdateCellButtonIDs.DISCARD:
            self.emit("source-discard", path, cu)
            self.expanded_path = None
        return False
