# -*- coding: utf-8 -*-
"""
Copyright (C) 2009 Canonical
Copyright (C) 2012 Fabio Erculiani

Authors:
  Michael Vogt
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
from gi.repository import Gtk, Gdk, GObject

from rigo.em import em, StockEms, Ems


class GenericTreeView(Gtk.TreeView):

    COL_ROW_DATA = 0

    def __init__(self, row_activated_callback, button_activated_callback, tr):
        self._row_activated_callback = row_activated_callback
        self._button_activated_callback = button_activated_callback
        Gtk.TreeView.__init__(self)
        self.pressed = False
        self.focal_btn = None
        self.expanded_path = None
        self.set_headers_visible(False)

        # custom cursor
        self._cursor_hand = Gdk.Cursor.new(Gdk.CursorType.HAND2)

        self.connect("style-updated", self._on_style_updated, tr)
        # button and motion are "special"
        self.connect("button-press-event", self._on_button_press_event, tr)
        self.connect("button-release-event", self._on_button_release_event, tr)
        self.connect("motion-notify-event", self._on_motion, tr)
        self.connect("cursor-changed", self._on_cursor_changed, tr)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated, tr)
        self._calc_row_heights(tr)

    @property
    def model(self):
        model = self.get_model()
        if isinstance(model, Gtk.TreeModelFilter):
            return model.get_model()
        return model

    def clear_selection(self):
        self.expanded_path = None
        self.focal_btn = None

    def clear_model(self):
        vadjustment = self.get_scrolled_window_vadjustment()
        if vadjustment:
            vadjustment.set_value(0)
        self.clear_selection()
        model = self.model
        if model:
            model.clear()

    def expand_path(self, path):
        if path is not None and not isinstance(path, Gtk.TreePath):
            raise TypeError(
                "Expects Gtk.TreePath or None, got %s" % type(path))

        model = self.get_model()
        old = self.expanded_path
        self.expanded_path = path

        if old is not None:
            try:
                # lazy solution to Bug #846204
                model.row_changed(old, model.get_iter(old))
            except Exception:
                pass

        if path is None:
            return
        model.row_changed(path, model.get_iter(path))

    def get_scrolled_window_vadjustment(self):
        ancestor = self.get_ancestor(Gtk.ScrolledWindow)
        if ancestor:
            return ancestor.get_vadjustment()

    def get_rowref(self, model, path):
        if path is None:
            return None
        return model[path][self.COL_ROW_DATA]

    def _calc_row_heights(self, tr):
        ypad = StockEms.SMALL
        tr.set_property('xpad', StockEms.MEDIUM)
        tr.set_property('ypad', ypad)

        btn = None
        for btn in tr.get_buttons():
            # recalc button geometry and cache
            btn.configure_geometry(self.create_pango_layout(""))

        if btn is None:
            btn_h = 0
        else:
            btn_h = btn.height

        normal_height = max(32 + 4*ypad, em(2.5) + 4*ypad)
        tr.normal_height = normal_height
        medium = StockEms.MEDIUM
        tr.selected_height = tr.normal_height + btn_h + medium

    def _on_style_updated(self, widget, tr):
        self._calc_row_heights(tr)

    def _on_motion(self, tree, event, tr):
        window = self.get_window()
        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y):
            window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path:
            window.set_cursor(None)
            return

        rowref = self.get_rowref(tree.get_model(), path[0])
        if not rowref:
            return

        use_hand = False
        for btn in tr.get_buttons():
            if btn.state == Gtk.StateFlags.INSENSITIVE:
                continue

            if btn.point_in(x, y):
                use_hand = True
                if self.focal_btn is btn:
                    btn.set_state(Gtk.StateFlags.ACTIVE)
                elif not self.pressed:
                    btn.set_state(Gtk.StateFlags.PRELIGHT)
            else:
                if btn.state != Gtk.StateFlags.NORMAL:
                    btn.set_state(Gtk.StateFlags.NORMAL)

        if use_hand:
            window.set_cursor(self._cursor_hand)
        else:
            window.set_cursor(None)

    def _on_cursor_changed(self, view, tr):
        model = view.get_model()
        sel = view.get_selection()
        path = view.get_cursor()[0]

        rowref = self.get_rowref(model, path)
        if not rowref:
            return

        if self.has_focus():
            self.grab_focus()

        sel.select_path(path)
        self._update_selected_row(view, tr, path)

    def _update_selected_row(self, view, tr, path=None):
        sel = view.get_selection()
        if not sel:
            return False
        model, rows = sel.get_selected_rows()
        if not rows:
            return False
        row = rows[0]

        # update active app, use row-ref as argument
        self.expand_path(row)
        return False

    def _on_row_activated(self, view, path, column, tr):
        rowref = self.get_rowref(view.get_model(), path)

        if not rowref:
            return

        x, y = self.get_pointer()
        for btn in tr.get_buttons():
            if btn.point_in(x, y):
                return
        self._row_activated_callback(path, rowref)

    def _on_button_event_get_path(self, view, event):
        if event.button != 1:
            return False

        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return False

        path = res[0]
        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return False

        return path

    def _on_button_press_event(self, view, event, tr):
        if not self._on_button_event_get_path(view, event):
            return

        self.pressed = True
        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and \
                    (btn.state != Gtk.StateFlags.INSENSITIVE):
                self.focal_btn = btn
                btn.set_state(Gtk.StateFlags.ACTIVE)
                view.queue_draw()
                return
        self.focal_btn = None

    def _on_button_release_event(self, view, event, tr):
        path = self._on_button_event_get_path(view, event)
        if not path:
            return

        self.pressed = False
        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and \
                    (btn.state != Gtk.StateFlags.INSENSITIVE):
                btn.set_state(Gtk.StateFlags.NORMAL)
                self.get_window().set_cursor(self._cursor_hand)
                if self.focal_btn is not btn:
                    break
                self._init_activated(btn, view.get_model(), path)
                view.queue_draw()
                break
        self.focal_btn = None

    def _init_activated(self, btn, model, path):
        obj = model[path][self.COL_ROW_DATA]
        s = Gtk.Settings.get_default()
        GObject.timeout_add(
            s.get_property("gtk-timeout-initial"),
            self._activated_callback,
            btn, btn.name, obj, model, path)

    def _cell_data_func_cb(self, col, cell, model, it, user_data):
        path = model.get_path(it)
        is_active = path == self.expanded_path
        cell.set_property('isactive', is_active)

    def _activated_callback(self, btn, btn_id, obj, store, path):
        if self._button_activated_callback is not None:
            return self._button_activated_callback(
                btn, btn_id, obj, store, path)
        return False

    def _set_cursor(self, btn, cursor):
        window = self.get_window()
        if isinstance(window, Gdk.Window):
            x, y = self.get_pointer()
            if btn.point_in(x, y):
                window.set_cursor(cursor)

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        if not res:
            return False
        return self.get_path_at_pos(x, y)[0] == self.get_cursor()[0]
