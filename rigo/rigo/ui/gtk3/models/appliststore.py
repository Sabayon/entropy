import os
from threading import Lock

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
                             (GObject.TYPE_PYOBJECT, ),
                             ),
    }

    def __init__(self, entropy_client, entropy_ws, view, icons):
        Gtk.ListStore.__init__(self)
        self._view = view
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
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

    def get_icon(self, pkg_match):
        cached = AppListStore._ICON_CACHE.get(pkg_match)
        if cached is not None:
            return cached

        def _ui_redraw_callback(*args):
            if const_debug_enabled():
                const_debug_write(__name__,
                                  "_ui_redraw_callback()")
            self.emit("redraw-request", pkg_match)
        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=_ui_redraw_callback)
        icon, cache_hit = app.get_details().icon
        if icon is None:
            if cache_hit:
                # this means that there is no icon for package
                # and so we should not keep bugging underlying
                # layers with requests
                AppListStore._ICON_CACHE[pkg_match] = self._missing_icon
            return self._missing_icon

        icon_path = icon.local_document()
        if not os.path.isfile(icon_path):
            return self._missing_icon

        img = Gtk.Image()
        img.set_from_file(icon_path)
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

    def is_installed(self, pkg_match):
        def _ui_redraw_callback(*args):
            if const_debug_enabled():
                const_debug_write(__name__,
                                  "_ui_redraw_callback()")
            self.emit("redraw-request", pkg_match)

        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=_ui_redraw_callback)
        return app.is_installed()

    def is_available(self, pkg_match):
        def _ui_redraw_callback(*args):
            if const_debug_enabled():
                const_debug_write(__name__,
                                  "_ui_redraw_callback()")
            self.emit("redraw-request", pkg_match)

        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=_ui_redraw_callback)
        return app.is_available()

    def get_markup(self, pkg_match):
        def _ui_redraw_callback(*args):
            if const_debug_enabled():
                const_debug_write(__name__,
                                  "_ui_redraw_callback()")
            self.emit("redraw-request", pkg_match)

        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=_ui_redraw_callback)
        return app.get_markup()

    def get_review_stats(self, pkg_match):
        def _ui_redraw_callback(*args):
            if const_debug_enabled():
                const_debug_write(__name__,
                                  "_ui_redraw_callback()")
            self.emit("redraw-request", pkg_match)

        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=_ui_redraw_callback)
        return app.get_review_stats()

    def get_application(self, pkg_match):
        def _ui_redraw_callback(*args):
            if const_debug_enabled():
                const_debug_write(__name__,
                                  "_ui_redraw_callback()")
            self.emit("redraw-request", pkg_match)

        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=_ui_redraw_callback)
        return app

    def get_transaction_progress(self, pkg_match):
        # FIXME, lxnay complete this
        # int from 0 - 100, or -1 for no transaction
        return -1
