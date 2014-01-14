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
from gi.repository import Gtk, Gdk, GObject
import os
from threading import Timer

from entropy.i18n import _

from .cellrenderers import CellRendererAppView, CellButtonRenderer, \
    CellButtonIDs

from rigo.em import em, StockEms
from rigo.enums import Icons, AppActions
from rigo.models.application import Application
from rigo.ui.gtk3.widgets.generictreeview import GenericTreeView

from RigoDaemon.enums import AppActions as DaemonAppActions, \
    ActivityStates as DaemonActivityStates


class AppTreeView(GenericTreeView):

    VARIANT_INFO = 0
    VARIANT_REMOVE = 1
    VARIANT_INSTALL = 2
    VARIANT_INSTALLING = 3
    VARIANT_REMOVING = 4
    VARIANT_UPDATE = 5
    COL_ROW_DATA = 0

    def __init__(self, entropy_client, rigo_service, apc, icons, show_ratings,
                 icon_size, store=None):
        Gtk.TreeView.__init__(self)

        self._scrolling_timer = None
        self._scrolled_view = None
        self._scrolled_view_vadj = None
        def _is_scrolling():
            return self._scrolling_timer is not None

        self._entropy = entropy_client
        self._apc = apc
        self._service = rigo_service

        tr = CellRendererAppView(icons,
                                 self.create_pango_layout(""),
                                 show_ratings,
                                 Icons.INSTALLED_OVERLAY,
                                 scrolling_cb=_is_scrolling)
        tr.set_pixbuf_width(icon_size)

        # create buttons and set initial strings
        info = CellButtonRenderer(
            self, name=CellButtonIDs.INFO)
        info.set_markup_variants(
                    {self.VARIANT_INFO: _('More Info')})

        action = CellButtonRenderer(
            self, name=CellButtonIDs.ACTION)
        action.set_markup_variants(
                {self.VARIANT_INSTALL: _('Install'),
                 self.VARIANT_REMOVE: _('Remove'),
                 self.VARIANT_UPDATE: _('Update'),
                 self.VARIANT_INSTALLING: _('Installing'),
                 self.VARIANT_REMOVING: _('Removing'),})

        tr.button_pack_start(info)
        tr.button_pack_end(action)

        GenericTreeView.__init__(
            self, self._row_activated_callback,
            self._button_activated_callback, tr)

        column = Gtk.TreeViewColumn(
            "Applications", tr,
            application=self.COL_ROW_DATA)
        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(200)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(column)

        self.connect("key-press-event", self._on_key_press_event, tr)
        self.connect("key-release-event", self._on_key_release_event, tr)

        self._service.connect(
            "application-processed",
            self._on_transaction_finished, tr)
        self._service.connect(
            "application-processing",
            self._on_transaction_started, tr)
        self._service.connect(
            "application-abort",
            self._on_transaction_stopped, tr)

        self.set_search_column(0)
        self.set_search_equal_func(self._app_search, None)
        self.set_property("enable-search", True)

    def _is_upgrade(self):
        """
        Return whether the system is currently being upgraded.
        """
        return self._service.activity() == DaemonActivityStates.UPGRADING_SYSTEM

    def _scrolling_event(self, vadj):
        """
        Event received from the Gtk.VAdjustment of the
        Gtk.ScrolledView containing this widget.
        We expose the scrolling state to upper and lower layers.
        """
        if self._scrolling_timer:
            return

        def unset():
            # This may cause a race condition
            # because an event of the past can
            # reset the state right after scrolling_timer
            # has been back set. But we don't really care in
            # this case. We don't want to be *that* precise.
            self._scrolling_timer = None

        def set_timer():
            t = Timer(1.0, unset)
            t.name = "UnsetScrollingTimer"
            t.daemon = True
            return t

        t = self._scrolling_timer
        if t is not None:
            t.cancel()

        t = set_timer()
        t.start()
        self._scrolling_timer = t

    def set_scrolled_view(self, scrolled_view):
        """
        Set the Gtk.ScrolledView container of this TreeView.
        """
        vadj = scrolled_view.get_vadjustment()
        vadj.connect("value-changed", self._scrolling_event)
        self._scrolled_view = scrolled_view
        self._scrolled_view_vadj = vadj

    def get_vadjustment(self):
        sv = self._scrolled_view
        if sv:
            return sv.get_vadjustment()

    def _row_activated_callback(self, path, rowref):
        self._apc.emit("application-activated",
                       self.model.get_application(rowref))

    def _app_search(self, model, column, key, iterator, data):
        pkg_match = model.get_value(iterator, 0)
        if pkg_match is None:
            return False
        app = Application(self._entropy, None, self._service, pkg_match)
        return not app.search(key)

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
        pkg_match = model[row][self.COL_ROW_DATA]

        action_btn = tr.get_button_by_name(
                            CellButtonIDs.ACTION)
        #if not action_btn: return False

        app = self.model.get_application(pkg_match)
        app_action = self._get_app_transaction(app)

        if self._is_upgrade():
            # System is being upgraded, do not show any buttons.
            action_btn.set_sensitive(False)
            action_btn.hide()

        elif app_action is None:
            if app.is_installed():
                # if we're not showing an Installed
                # Application and there is an update available
                # then show "Update" instead of "Remove"
                # bug #3417
                _variant = self.VARIANT_REMOVE
                if not app.is_installed_app():
                    if app.is_updatable():
                        _variant = self.VARIANT_UPDATE
                action_btn.set_variant(_variant)
                action_btn.set_sensitive(True)
                action_btn.show()
            elif app.is_available():
                action_btn.set_variant(self.VARIANT_INSTALL)
                action_btn.set_sensitive(True)
                action_btn.show()
            else:
                action_btn.set_sensitive(False)
                action_btn.hide()
                self._apc.emit("application-selected",
                               app)
                return

            if self.pressed and self.focal_btn == action_btn:
                action_btn.set_state(Gtk.StateFlags.ACTIVE)
            else:
                action_btn.set_state(Gtk.StateFlags.NORMAL)

        else:
            if app_action == AppActions.INSTALL:
                action_btn.set_variant(self.VARIANT_INSTALLING)
                action_btn.set_sensitive(False)
                action_btn.show()
            elif app_action == AppActions.REMOVE:
                action_btn.set_variant(self.VARIANT_REMOVING)
                action_btn.set_sensitive(False)
                action_btn.show()
            action_btn.set_state(Gtk.StateFlags.INSENSITIVE)

        self._apc.emit("application-selected", app)
        return False

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

    def _button_activated_callback(self, btn, btn_id, pkg_match, store, path):

        if isinstance(store, Gtk.TreeModelFilter):
            store = store.get_model()

        app = self.model.get_application(pkg_match)
        if btn_id == CellButtonIDs.INFO:
            self._apc.emit("application-activated", app)
        elif btn_id == CellButtonIDs.ACTION:
            btn.set_sensitive(False)
            store.row_changed(path, store.get_iter(path))

            if self._is_upgrade():
                # System is being upgraded, do not show activate any buttons.
                return False

            # be sure we dont request an action for a
            # pkg with pre-existing actions
            daemon_action = self._get_app_transaction(app)
            if daemon_action is not None:
                return False

            if btn.current_variant == self.VARIANT_REMOVE:
                perform_action = AppActions.REMOVE
                app = app.get_installed()
                if app is None:
                    return False
            else:
                perform_action = AppActions.INSTALL
            self._set_app_transaction(app, perform_action)

            self._apc.emit("application-request-action",
                           app, perform_action)
            self.queue_draw()
        return False

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

    def _on_transaction_finished(self, widget, app,
                                 daemon_action, app_outcome, tr):
        """
        callback when an application install/remove
        transaction has finished
        """
        self.emit("cursor-changed")
        # remove pkg from the block list
        self._pop_app_transaction(app)

        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            # just completed daemon_action
            sensitive = True
            if daemon_action == DaemonAppActions.INSTALL:
                if app.is_installed():
                    # if we're not showing an Installed
                    # Application and there is an update available
                    # then show "Update" instead of "Remove"
                    # bug #3417
                    _variant = self.VARIANT_REMOVE
                    if not app.is_installed_app():
                        if app.is_updatable():
                            _variant = self.VARIANT_UPDATE
                    action_btn.set_variant(_variant)
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
        self._pop_app_transaction(app)

        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            if daemon_action == DaemonAppActions.INSTALL:
                # if we're not showing an Installed
                # Application and there is an update available
                # then show "Update" instead of "Remove"
                # bug #3417
                _variant = self.VARIANT_INSTALL
                if app.is_updatable():
                    _variant = self.VARIANT_UPDATE
                action_btn.set_variant(_variant)
            elif daemon_action == DaemonAppActions.REMOVE:
                action_btn.set_variant(self.VARIANT_REMOVE)
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)
            self.queue_draw()

    def _get_app_transaction(self, app):
        """
        Get Application transaction state (AppAction enum).
        """
        pkg_match = app.get_details().pkg
        local_txs = self._service.local_transactions()
        tx = local_txs.get(pkg_match)
        if tx is None:
            tx = self._service.action(app)
            if tx == DaemonAppActions.IDLE:
                tx = None
        return tx

    def _set_app_transaction(self, app, daemon_action):
        """
        Set Application local transaction state (AppAction enum).
        """
        pkg_match = app.get_details().pkg
        local_txs = self._service.local_transactions()
        local_txs[pkg_match] = daemon_action

    def _pop_app_transaction(self, app):
        """
        Drop Application local transaction state.
        """
        pkg_match = app.get_details().pkg
        local_txs = self._service.local_transactions()
        action = local_txs.pop(pkg_match, None)
        return action
