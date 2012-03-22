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
import logging
import os

from entropy.i18n import _

from cellrenderers import CellRendererAppView, CellButtonRenderer, \
    CellButtonIDs

from rigo.em import em, StockEms
from rigo.enums import Icons, AppActions
from rigo.models.application import CategoryRowReference, Application

from RigoDaemon.enums import AppActions as DaemonAppActions

COL_ROW_DATA = 0

class AppTreeView(Gtk.TreeView):

    """Treeview based view component that takes a AppStore and displays it"""

    VARIANT_INFO = 0
    VARIANT_REMOVE = 1
    VARIANT_INSTALL = 2
    VARIANT_INSTALLING = 3
    VARIANT_REMOVING = 4

    def __init__(self, entropy_client, backend, apc, icons, show_ratings,
                 icon_size, store=None):
        Gtk.TreeView.__init__(self)
        self._logger = logging.getLogger(__name__)

        self._entropy = entropy_client
        self._apc = apc
        self._backend = backend

        self.pressed = False
        self.focal_btn = None
        # pkg match is key, AppAction is val
        self._action_block_list = {}
        self.expanded_path = None

        #~ # if this hacked mode is available everything will be fast
        #~ # and we can set fixed_height mode and still have growing rows
        #~ # (see upstream gnome #607447)
        try:
            self.set_property("ubuntu-almost-fixed-height-mode", True)
            self.set_fixed_height_mode(True)
        except:
            self._logger.warn("ubuntu-almost-fixed-height-mode extension not available")

        self.set_headers_visible(False)

        # a11y: this is a cell renderer that only displays a icon, but still
        #       has a markup property for orca and friends
        # we use it so that orca and other a11y tools get proper text to read
        # it needs to be the first one, because that is what the tools look
        # at by default
        tr = CellRendererAppView(icons,
                                 self.create_pango_layout(""),
                                 show_ratings,
                                 Icons.INSTALLED_OVERLAY)
        tr.set_pixbuf_width(icon_size)

        tr.set_button_spacing(em(0.3))

        # create buttons and set initial strings
        info = CellButtonRenderer(self,
                                  name=CellButtonIDs.INFO)
        info.set_markup_variants(
                    {self.VARIANT_INFO: _('More Info')})

        action = CellButtonRenderer(self,
                                    name=CellButtonIDs.ACTION)
        action.set_markup_variants(
                {self.VARIANT_INSTALL: _('Install'),
                 self.VARIANT_REMOVE: _('Remove'),
                 self.VARIANT_INSTALLING: _('Installing'),
                 self.VARIANT_REMOVING: _('Removing'),})

        tr.button_pack_start(info)
        tr.button_pack_end(action)

        column = Gtk.TreeViewColumn("Applications", tr,
                                    application=COL_ROW_DATA)
        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(200)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(column)

        # custom cursor
        self._cursor_hand = Gdk.Cursor.new(Gdk.CursorType.HAND2)

        self.connect("style-updated", self._on_style_updated, tr)
        # button and motion are "special"
        self.connect("button-press-event", self._on_button_press_event, tr)
        self.connect("button-release-event", self._on_button_release_event, tr)
        self.connect("key-press-event", self._on_key_press_event, tr)
        self.connect("key-release-event", self._on_key_release_event, tr)
        self.connect("motion-notify-event", self._on_motion, tr)
        self.connect("cursor-changed", self._on_cursor_changed, tr)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated, tr)

        self._backend.connect(
            "application-processed",
            self._on_transaction_finished, tr)
        self._backend.connect(
            "application-processing",
            self._on_transaction_started, tr)
        self._backend.connect(
            "application-abort",
            self._on_transaction_stopped, tr)

        self.set_search_column(0)
        self.set_search_equal_func(self._app_search, None)
        self.set_property("enable-search", True)


    def _app_search(self, model, column, key, iterator, data):
        pkg_match = model.get_value(iterator, 0)
        if pkg_match is None:
            return False
        app = Application(self._entropy, None, pkg_match)
        return not app.search(key)

    @property
    def appmodel(self):
        model = self.get_model()
        if isinstance(model, Gtk.TreeModelFilter):
            return model.get_model()
        return model

    def clear_model(self):
        vadjustment = self.get_scrolled_window_vadjustment()
        if vadjustment:
            vadjustment.set_value(0)
        self.expanded_path = None
        if self.appmodel:
            self.appmodel.clear()

    def expand_path(self, path):
        if path is not None and not isinstance(path, Gtk.TreePath):
            raise TypeError("Expects Gtk.TreePath or None, got %s" % type(path))

        model = self.get_model()
        old = self.expanded_path
        self.expanded_path = path

        if old is not None:
            try:
                # lazy solution to Bug #846204
                model.row_changed(old, model.get_iter(old))
            except:
                msg = "apptreeview.expand_path: Supplied 'old' path is an invalid tree path: '%s'" % old
                logging.debug(msg)
        if path == None: return

        model.row_changed(path, model.get_iter(path))
        return

    def get_scrolled_window_vadjustment(self):
        ancestor = self.get_ancestor(Gtk.ScrolledWindow)
        if ancestor:
            return ancestor.get_vadjustment()
        return None

    def get_rowref(self, model, path):
        if path == None: return None
        return model[path][COL_ROW_DATA]

    def rowref_is_category(self, rowref):
        return isinstance(rowref, CategoryRowReference)

    def _calc_row_heights(self, tr):
        ypad = StockEms.SMALL
        tr.set_property('xpad', StockEms.MEDIUM)
        tr.set_property('ypad', ypad)

        for btn in tr.get_buttons():
            # recalc button geometry and cache
            btn.configure_geometry(self.create_pango_layout(""))

        btn_h = btn.height

        tr.normal_height = max(32 + 4*ypad, em(2.5) + 4*ypad)
        tr.selected_height = tr.normal_height + btn_h + StockEms.MEDIUM
        return

    def _on_style_updated(self, widget, tr):
        self._calc_row_heights(tr)
        return

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
        if not rowref: return

        if self.rowref_is_category(rowref):
            window.set_cursor(None)
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
        return

    def _on_cursor_changed(self, view, tr):
        model = view.get_model()
        sel = view.get_selection()
        path = view.get_cursor()[0]

        rowref = self.get_rowref(model, path)
        if not rowref: return

        if self.has_focus(): self.grab_focus()

        if self.rowref_is_category(rowref):
            self.expand_path(None)
            return

        sel.select_path(path)
        self._update_selected_row(view, tr, path)
        return

    def _update_selected_row(self, view, tr, path=None):
        sel = view.get_selection()
        if not sel:
            return False
        model, rows = sel.get_selected_rows()
        if not rows:
            return False
        row = rows[0]
        if self.rowref_is_category(row):
            return False

        # update active app, use row-ref as argument
        self.expand_path(row)

        app = model[row][COL_ROW_DATA]

        # make sure this is not a category (LP: #848085)
        if self.rowref_is_category(app):
            return False

        action_btn = tr.get_button_by_name(
                            CellButtonIDs.ACTION)
        #if not action_btn: return False

        app_action = self._action_block_list.get(app)
        if app_action is None:
            if self.appmodel.is_installed(app):
                action_btn.set_variant(self.VARIANT_REMOVE)
                action_btn.set_sensitive(True)
                action_btn.show()
            elif self.appmodel.is_available(app):
                action_btn.set_variant(self.VARIANT_INSTALL)
                action_btn.set_sensitive(True)
                action_btn.show()
            else:
                action_btn.set_sensitive(False)
                action_btn.hide()
                self._apc.emit("application-selected",
                               self.appmodel.get_application(app))
                return
        else:
            if app_action == AppActions.INSTALL:
                action_btn.set_variant(self.VARIANT_INSTALLING)
                action_btn.set_sensitive(False)
                action_btn.show()
            elif app_action == AppActions.REMOVE:
                action_btn.set_variant(self.VARIANT_REMOVING)
                action_btn.set_sensitive(False)
                action_btn.show()

        if self.appmodel.get_transaction_progress(app) > 0:
            action_btn.set_sensitive(False)
        elif self.pressed and self.focal_btn == action_btn:
            action_btn.set_state(Gtk.StateFlags.ACTIVE)
        else:
            action_btn.set_state(Gtk.StateFlags.NORMAL)

        #~ self.emit("application-selected", self.appmodel.get_application(app))
        self._apc.emit("application-selected",
                           self.appmodel.get_application(app))
        return False

    def _on_row_activated(self, view, path, column, tr):
        rowref = self.get_rowref(view.get_model(), path)

        if not rowref: return

        if self.rowref_is_category(rowref): return

        x, y = self.get_pointer()
        for btn in tr.get_buttons():
            if btn.point_in(x, y):
                return

        self._apc.emit("application-activated",
                           self.appmodel.get_application(rowref))
        return

    def _on_button_event_get_path(self, view, event):
        if event.button != 1:
            return False

        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return False

        # check the path is valid and is not a category row
        path = res[0]
        is_cat = self.rowref_is_category(
            self.get_rowref(view.get_model(), path))
        if path is None or is_cat:
            return False

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
            if btn.point_in(x, y) and (btn.state != Gtk.StateFlags.INSENSITIVE):
                self.focal_btn = btn
                btn.set_state(Gtk.StateFlags.ACTIVE)
                view.queue_draw()
                return
        self.focal_btn = None
        return

    def _on_button_release_event(self, view, event, tr):
        path = self._on_button_event_get_path(view, event)
        if not path: return

        self.pressed = False
        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and (btn.state != Gtk.StateFlags.INSENSITIVE):
                btn.set_state(Gtk.StateFlags.NORMAL)
                self.get_window().set_cursor(self._cursor_hand)
                if self.focal_btn is not btn:
                    break
                self._init_activated(btn, view.get_model(), path)
                view.queue_draw()
                break
        self.focal_btn = None
        return

    def _on_key_press_event(self, widget, event, tr):
        kv = event.keyval
        #print kv
        r = False
        if kv == Gdk.KEY_Right: # right-key
            btn = tr.get_button_by_name(CellButtonIDs.ACTION)
            if btn is None:
                return  # Bug #846779
            if btn.state != Gtk.StateFlags.INSENSITIVE:
                btn.has_focus = True
                btn = tr.get_button_by_name(CellButtonIDs.INFO)
                btn.has_focus = False
        elif kv == Gdk.KEY_Left: # left-key
            btn = tr.get_button_by_name(CellButtonIDs.ACTION)
            if btn is None:
                return  # Bug #846779
            btn.has_focus = False
            btn = tr.get_button_by_name(CellButtonIDs.INFO)
            btn.has_focus = True
        elif kv == Gdk.KEY_space:  # spacebar
            for btn in tr.get_buttons():
                if (btn is not None and btn.has_focus and
                    btn.state != Gtk.StateFlags.INSENSITIVE):
                    btn.set_state(Gtk.StateFlags.ACTIVE)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    if path:
                        #self._init_activated(btn, self.get_model(), path)
                        r = True
                    break

        self.queue_draw()
        return r

    def _on_key_release_event(self, widget, event, tr):
        kv = event.keyval
        r = False
        if kv == 32:    # spacebar
            for btn in tr.get_buttons():
                if btn.has_focus and btn.state != Gtk.StateFlags.INSENSITIVE:
                    btn.set_state(Gtk.StateFlags.NORMAL)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    if path:
                        self._init_activated(btn, self.get_model(), path)
                        btn.has_focus = False
                        r = True
                    break

        self.queue_draw()
        return r

    def _init_activated(self, btn, model, path):
        app = model[path][COL_ROW_DATA]
        s = Gtk.Settings.get_default()
        GObject.timeout_add(s.get_property("gtk-timeout-initial"),
                            self._app_activated_cb,
                            btn,
                            btn.name,
                            app,
                            model,
                            path)
        return

    def _cell_data_func_cb(self, col, cell, model, it, user_data):

        path = model.get_path(it)

        if model[path][0] is None:
            indices = path.get_indices()
            model.load_range(indices, 5)

        is_active = path == self.expanded_path
        cell.set_property('isactive', is_active)
        return

    def _app_activated_cb(self, btn, btn_id, app, store, path):
        if self.rowref_is_category(app):
            return

        # FIXME: would be nice if that would be more elegant
        # because we use a treefilter we need to get the "real"
        # model first
        if type(store) is Gtk.TreeModelFilter:
            store = store.get_model()

        if btn_id == CellButtonIDs.INFO:
            self._apc.emit("application-activated",
                               self.appmodel.get_application(app))
        elif btn_id == CellButtonIDs.ACTION:
            btn.set_sensitive(False)
            store.row_changed(path, store.get_iter(path))
            # be sure we dont request an action for a
            # pkg with pre-existing actions
            if app in self._action_block_list:
                logging.debug(
                    "Action already in progress for match: %s" % (
                        (app,)))
                return False
            if self.appmodel.is_installed(app):
                perform_action = AppActions.REMOVE
            else:
                perform_action = AppActions.INSTALL
            self._action_block_list[app] = perform_action

            self._apc.emit("application-request-action",
                      self.appmodel.get_application(app),
                      perform_action)
        return False

    def _set_cursor(self, btn, cursor):
        # make sure we have a window instance (LP: #617004)
        window = self.get_window()
        if isinstance(window, Gdk.Window):
            x, y = self.get_pointer()
            if btn.point_in(x, y):
                window.set_cursor(cursor)

    def _on_transaction_started(self, widget, app, daemon_action, tr):
        """
        callback when an application install/remove
        transaction has started
        """
        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            if daemon_action == DaemonAppActions.INSTALL:
                action_btn.set_variant(self.VARIANT_INSTALLING)
            elif daemon_action == DaemonAppActions.REMOVE:
                action_btn.set_variant(self.VARIANT_REMOVING)
            action_btn.set_sensitive(False)
            self._set_cursor(action_btn, None)
            self.queue_draw()

    def _on_transaction_finished(self, widget, app, daemon_action, tr):
        """
        callback when an application install/remove
        transaction has finished
        """
        self.emit("cursor-changed")
        # remove pkg from the block list
        pkg = app.get_details().pkg
        self._check_remove_pkg_from_blocklist(pkg)

        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            # just completed daemon_action
            sensitive = True
            if daemon_action == DaemonAppActions.INSTALL:
                if app.is_installed():
                    action_btn.set_variant(self.VARIANT_REMOVE)
                elif app.is_available():
                    action_btn.set_variant(self.VARIANT_INSTALL)
                else:
                    action_btn.set_variant(self.VARIANT_INSTALL)
                    sensitive = False
                    # wtf?

            elif daemon_action == DaemonAppActions.REMOVE:
                if app.is_available():
                    action_btn.set_variant(self.VARIANT_INSTALL)
                elif app.is_installed():
                    action_btn.set_variant(self.VARIANT_REMOVE)
                else:
                    action_btn.set_variant(self.VARIANT_INSTALL)
                    sensitive = False
                    # wtf?

            action_btn.set_sensitive(sensitive)
            if sensitive:
                self._set_cursor(action_btn, self._cursor_hand)
            else:
                self._set_cursor(action_btn, None)
            self.queue_draw()

    def _on_transaction_stopped(self, widget, app, daemon_action, tr):
        """
        callback when an application install/remove
        transaction has stopped
        """
        pkg = app.get_details().pkg
        self._check_remove_pkg_from_blocklist(pkg)

        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            if daemon_action == DaemonAppActions.INSTALL:
                action_btn.set_variant(self.VARIANT_INSTALL)
            elif daemon_action == DaemonAppActions.REMOVE:
                action_btn.set_variant(self.VARIANT_REMOVE)
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)
            self.queue_draw()

    def _check_remove_pkg_from_blocklist(self, app):
        action = self._action_block_list.pop(app, None)
        return action

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        #cur = self.get_cursor()
        if not res:
            return False
        return self.get_path_at_pos(x, y)[0] == self.get_cursor()[0]


def on_entry_changed(widget, data):

    def _work():
        new_text = widget.get_text()
        (view, enquirer) = data

        # FIXME lxnay
        enquirer.set_query(get_query_from_search_entry(new_text),
                           limit=100*1000,
                           nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE)

        store = view.tree_view.get_model()
        store.clear()

        store.set_from_matches(enquirer.matches)

        while Gtk.events_pending():
            Gtk.main_iteration()

    if widget.stamp:
        GObject.source_remove(widget.stamp)
        widget.stamp = GObject.timeout_add(250, _work)

