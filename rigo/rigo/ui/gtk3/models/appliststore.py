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
import os
from threading import Lock, Semaphore

from gi.repository import Gtk, GLib, GObject, GdkPixbuf

from rigo.enums import Icons
from rigo.models.application import Application, ApplicationMetadata

from entropy.const import const_debug_write, const_debug_enabled


class AppListStore(Gtk.ListStore):

    # column types
    COL_TYPES = (GObject.TYPE_PYOBJECT,)

    # column id
    COL_ROW_DATA = 0

    # default icon size returned by Application.get_icon()
    ICON_SIZE = 48
    _MISSING_ICON = None
    _MISSING_ICON_MUTEX = Lock()
    _ICON_CACHE = {}

    __gsignals__ = {
        # Redraw signal, requesting UI update
        # for given pkg_match object
        "redraw-request"  : (GObject.SignalFlags.RUN_LAST,
                             None,
                             (GObject.TYPE_PYOBJECT,),
                             ),
        # signal that all the elements in the List
        # have vanished.
        "all-vanished"    : (GObject.SignalFlags.RUN_LAST,
                             None,
                             tuple(),
                             ),
    }

    def __init__(self, entropy_client, entropy_ws, rigo_service,
                 view, icons):
        Gtk.ListStore.__init__(self)
        self._view = view
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._service = rigo_service
        self._icons = icons
        self.set_column_types(self.COL_TYPES)

        # Startup Entropy Package Metadata daemon
        ApplicationMetadata.start()

    def clear(self):
        """
        Clear ListStore content (and Icon Cache).
        """
        outcome = Gtk.ListStore.clear(self)
        AppListStore._ICON_CACHE.clear()
        return outcome

    @property
    def _missing_icon(self):
        """
        Return the missing icon Gtk.Image() if needed.
        """
        if AppListStore._MISSING_ICON is not None:
            return AppListStore._MISSING_ICON
        with AppListStore._MISSING_ICON_MUTEX:
            if AppListStore._MISSING_ICON is not None:
                return AppListStore._MISSING_ICON
            _missing_icon = self._icons.load_icon(
            Icons.MISSING_APP, AppListStore.ICON_SIZE, 0)
            AppListStore._MISSING_ICON = _missing_icon
            return _missing_icon

    def visible(self, pkg_match):
        """
        Returns whether Application (through pkg_match) is still
        visible in the TreeView.
        This method shall be Thread safe.
        """
        s_data = {
            'sem': Semaphore(0),
            'res': None,
        }

        def _get_visible(data):
            res = False
            try:
                vis_data = self._view.get_visible_range()
                if vis_data is None:
                    return
                if len(vis_data) == 2:
                    # Gtk 3.4
                    valid_paths = True
                    start_path, end_path = vis_data
                else:
                    # Gtk <3.2
                    valid_paths, start_path, end_path = vis_data

                if not valid_paths:
                    return

                path = start_path
                while path <= end_path:
                    path_iter = self.get_iter(path)
                    if self.iter_is_valid(path_iter):
                        visible_pkg_match = self.get_value(path_iter, 0)
                        if visible_pkg_match == pkg_match:
                            res = True
                            return
                    path.next()
                res = False
            finally:
                data['res'] = res
                data['sem'].release()

        GLib.idle_add(_get_visible, s_data)
        s_data['sem'].acquire()

        return s_data['res']

    def get_icon(self, app, cached=False):

        pkg_match = app.get_details().pkg
        cached_icon = AppListStore._ICON_CACHE.get(pkg_match)
        if cached_icon is not None:
            return cached_icon
        if cached:
            # then return the default icon
            return self._missing_icon

        def _still_visible():
            return self.visible(pkg_match)

        icon, cache_hit = app.get_icon(
            _still_visible_cb=_still_visible,
            cached=cached)
        if const_debug_enabled():
            const_debug_write(__name__,
                              "get_icon({%s, %s}) = %s, hit: %s" % (
                    (pkg_match, app.name, icon, cache_hit,)))

        if icon is None:
            if cache_hit:
                # this means that there is no icon for package
                # and so we should not keep bugging underlying
                # layers with requests
                AppListStore._ICON_CACHE[pkg_match] = self._missing_icon
            return self._missing_icon

        icon_path = icon.local_document()
        icon_path_exists = False
        if icon_path:
            icon_path_exists = os.path.isfile(icon_path)
        if not icon_path_exists:
            return self._missing_icon

        try:
            img = Gtk.Image.new_from_file(icon_path)
        except GObject.GError:
            return self._missing_icon

        img_buf = img.get_pixbuf()
        if img_buf is None:
            # wth, invalid crap
            return self._missing_icon
        w, h = img_buf.get_width(), img_buf.get_height()
        del img_buf
        del img
        if w < 1:
            # not legit
            return self._missing_icon
        width = AppListStore.ICON_SIZE
        height = width * h / w

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                icon_path, width, height)
        except GObject.GError:
            try:
                os.remove(icon_path)
            except OSError:
                pass
            return self._missing_icon

        AppListStore._ICON_CACHE[pkg_match] = pixbuf
        return pixbuf

    def _vanished_callback(self, app):
        """
        Remove elements that are marked as "vanished" due
        to unavailable metadata.
        """
        def _remove(_app):
            pkg_match = _app.get_details().pkg

            vis_data = self._view.get_visible_range()
            if vis_data is None:
                return
            if len(vis_data) == 2:
                # Gtk 3.4
                valid_paths = True
                start_path, end_path = vis_data
            else:
                # Gtk <3.2
                valid_paths, start_path, end_path = vis_data

            if not valid_paths:
                return

            path = start_path
            while path <= end_path:
                path_iter = self.get_iter(path)
                if self.iter_is_valid(path_iter):
                    visible_pkg_match = self.get_value(path_iter, 0)
                    if visible_pkg_match == pkg_match:
                        self.remove(path_iter)
                        if len(self) == 0:
                            self.emit("all-vanished")
                        return
                path.next()

        GLib.idle_add(_remove, app)

    def get_application(self, pkg_match):
        def _ui_redraw_callback(*args):
            if const_debug_enabled():
                const_debug_write(__name__,
                                  "_ui_redraw_callback()")
            GLib.idle_add(self.emit, "redraw-request", pkg_match)

        app = Application(self._entropy, self._entropy_ws,
                          self._service, pkg_match,
                          redraw_callback=_ui_redraw_callback,
                          vanished_callback=self._vanished_callback)
        return app
