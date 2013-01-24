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

from .cellrenderers import CellButtonRenderer, CellRendererRepositoryView, \
    RepositoryCellButtonIDs

from rigo.ui.gtk3.models.repositoryliststore import RepositoryListStore
from rigo.ui.gtk3.widgets.generictreeview import GenericTreeView


class RepositoryTreeView(GenericTreeView):

    VARIANT_ENABLE = 0
    VARIANT_DISABLE = 1
    VARIANT_RENAME = 2

    __gsignals__ = {
        # Enable/Disable repository
        "toggle-repo" : (GObject.SignalFlags.RUN_LAST,
                         None,
                         (GObject.TYPE_PYOBJECT,
                          GObject.TYPE_PYOBJECT),
                         ),
        # Rename repository event
        "rename-repo" : (GObject.SignalFlags.RUN_LAST,
                         None,
                         (GObject.TYPE_PYOBJECT,
                          GObject.TYPE_PYOBJECT),
                         ),
        }

    def __init__(self, icons, icon_size):
        Gtk.TreeView.__init__(self)

        tr = CellRendererRepositoryView(
            icons, RepositoryListStore.ICON_SIZE,
            self.create_pango_layout(""))
        tr.set_pixbuf_width(icon_size)

        toggle_repo = CellButtonRenderer(
            self, name=RepositoryCellButtonIDs.TOGGLE)
        toggle_repo.set_markup_variants(
            {self.VARIANT_ENABLE: _("Enable"),
             self.VARIANT_DISABLE: _("Disable")})
        tr.button_pack_end(toggle_repo)

        rename_repo = CellButtonRenderer(
            self, name=RepositoryCellButtonIDs.RENAME)
        rename_repo.set_markup_variants(
            {self.VARIANT_RENAME: _("Rename")})
        tr.button_pack_start(rename_repo)

        column = Gtk.TreeViewColumn("Repositories", tr,
                                    repository=self.COL_ROW_DATA)

        GenericTreeView.__init__(
            self, None,
            self._button_activated_callback, tr)

        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(350)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(column)

    def _update_selected_row(self, view, tr, path=None):
        sel = view.get_selection()
        if not sel:
            return False
        model, rows = sel.get_selected_rows()
        if not rows:
            return False
        row = rows[0]

        self.expand_path(row)
        repository = model[row][self.COL_ROW_DATA]

        toggle_btn = tr.get_button_by_name(
            RepositoryCellButtonIDs.TOGGLE)
        rename_btn = tr.get_button_by_name(
            RepositoryCellButtonIDs.RENAME)

        if repository.enabled():
            toggle_btn.set_variant(self.VARIANT_DISABLE)
        else:
            toggle_btn.set_variant(self.VARIANT_ENABLE)
        if self.pressed and self.focal_btn == toggle_btn:
            toggle_btn.set_state(Gtk.StateFlags.ACTIVE)
        else:
            toggle_btn.set_state(Gtk.StateFlags.NORMAL)
        toggle_btn.set_sensitive(True)
        toggle_btn.show()

        if self.pressed and self.focal_btn == rename_btn:
            rename_btn.set_state(Gtk.StateFlags.ACTIVE)
        else:
            rename_btn.set_state(Gtk.StateFlags.NORMAL)
        rename_btn.set_variant(self.VARIANT_RENAME)
        rename_btn.set_sensitive(True)
        rename_btn.show()

        return False

    def _button_activated_callback(self, btn, btn_id, repo, store, path):
        if isinstance(store, Gtk.TreeModelFilter):
            store = store.get_model()
        if btn_id == RepositoryCellButtonIDs.TOGGLE:
            self.emit("toggle-repo", path, repo)
            btn.set_sensitive(False)
        elif btn_id == RepositoryCellButtonIDs.RENAME:
            self.emit("rename-repo", path, repo)
            btn.set_sensitive(False)
        return False
