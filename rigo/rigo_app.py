import os
import sys
import copy
import tempfile
from threading import Lock

sys.path.insert(0, "../lib")
sys.path.insert(1, "../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/lib")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/rigo")


from gi.repository import Gtk, Gdk, Gio, GLib, GObject, GdkPixbuf

from rigo.paths import DATA_DIR
from rigo.enums import Icons
from rigo.models.application import Application, ApplicationMetadata
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme, \
    resize_image

from entropy.const import etpUi, const_debug_write, const_debug_enabled
from entropy.exceptions import RepositoryError
from entropy.client.interfaces import Client
from entropy.services.client import WebService
from entropy.misc import TimeScheduled, ParallelTask
from entropy.i18n import _

import entropy.tools

class EntropyWebService(object):

    def __init__(self, entropy_client, tx_callback=None):
        # Install custom CACHE_DIR pointing it to our
        # home directory. This way we don't need to mess
        # with privileges, resulting in documents not
        # downloadable.
        home_dir = os.getenv("HOME")
        if home_dir is None:
            home_dir = tempfile.mkdtemp(prefix="EntropyWebService")
        ws_cache_dir = os.path.join(home_dir, ".entropy", "ws_cache")
        WebService.CACHE_DIR = ws_cache_dir
        self._entropy = entropy_client
        self._webserv_map = {}
        self._tx_callback = tx_callback
        self._mutex = Lock()

    def get(self, repository_id):
        """
        Get Entropy Web Services service object (ClientWebService).

        @param repository_id: repository identifier
        @type repository_id: string
        @return: the ClientWebService instance
        @rtype: entropy.client.services.interfaces.ClientWebService
        @raise WebService.UnsupportedService: if service is unsupported by
        repository
        """
        webserv = self._webserv_map.get(repository_id)
        if webserv == -1:
            # not available
            return None
        if webserv is not None:
            return webserv

        with self._mutex:
            webserv = self._webserv_map.get(repository_id)
            if webserv == -1:
                # not available
                return None
            if webserv is not None:
                return webserv

            try:
                webserv = self._get(self._entropy, repository_id)
            except WebService.UnsupportedService as err:
                webserv = None

        if webserv is None:
            self._webserv_map[repository_id] = -1
            # not available
            return None

        try:
            available = webserv.service_available()
        except WebService.WebServiceException:
            available = False

        if not available:
            with self._mutex:
                if repository_id not in self._webserv_map:
                    self._webserv_map[repository_id] = -1
            return

        with self._mutex:
            if repository_id not in self._webserv_map:
                self._webserv_map[repository_id] = webserv
        return webserv

    def _get(self, entropy_client, repository_id):
        """
        Get Entropy Web Services service object (ClientWebService).

        @param entropy_client: Entropy Client interface
        @type entropy_client: entropy.client.interfaces.Client
        @param repository_id: repository identifier
        @type repository_id: string
        @return: the ClientWebService instance
        @rtype: entropy.client.services.interfaces.ClientWebService
        @raise WebService.UnsupportedService: if service is unsupported by
        repository
        """
        factory = entropy_client.WebServices()
        webserv = factory.new(repository_id)
        if self._tx_callback is not None:
            webserv._set_transfer_callback(self._tx_callback)
        return webserv


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

    def _ui_redraw_callback(self, *args):
        if const_debug_enabled():
            const_debug_write(__name__,
                              "_ui_redraw_callback()")
        GLib.idle_add(self._view.queue_draw)

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

        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
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
        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app.is_installed()

    def is_available(self, pkg_match):
        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app.is_available()

    def get_markup(self, pkg_match):
        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app.get_markup()

    def get_review_stats(self, pkg_match):
        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app.get_review_stats()

    def get_application(self, pkg_match):
        app = Application(self._entropy, self._entropy_ws, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app

    def get_transaction_progress(self, pkg_match):
        # TODO: complete
        # int from 0 - 100, or -1 for no transaction
        return -1


class PackagesViewController(object):

    def __init__(self, entropy_client, icons, entropy_ws, rigo_sm,
                 search_entry, view):
        self._entropy = entropy_client
        self._icons = icons
        self._rigo_sm = rigo_sm
        self._entropy_ws = entropy_ws
        self._search_entry = search_entry
        self._view = view

    def _search_icon_release(self, search_entry, icon_pos, _other):
        """
        Event associated to the Search bar icon click.
        Here we catch secondary icon click to reset the search entry text.
        """
        if search_entry is not self._search_entry:
            return
        if icon_pos != Gtk.EntryIconPosition.SECONDARY:
            return
        search_entry.set_text("")
        self.clear()
        search_entry.emit("changed")

    def _search_changed(self, search_entry):
        GLib.timeout_add(700, self._search, search_entry.get_text())

    def _search(self, old_text):
        cur_text = self._search_entry.get_text()
        if cur_text == old_text and cur_text:
            th = ParallelTask(self.__search_thread, copy.copy(old_text))
            th.name = "SearchThread"
            th.start()

    def __search_thread(self, text):
        matches = []
        pkg_matches, rc = self._entropy.atom_match(
            text, multi_match = True,
            multi_repo = True, mask_filter = False)
        matches.extend(pkg_matches)
        search_matches = self._entropy.atom_search(
            text, repositories = self._entropy.repositories())
        matches.extend([x for x in search_matches if x not in matches])
        self.clear_safe()
        self.append_many_safe(matches)

    def setup(self):
        self._store = AppListStore(
            self._entropy, self._entropy_ws,
            self._view, self._icons)
        self._view.set_model(self._store)

        # setup searchEntry event
        self._search_entry.connect(
            "changed", self._search_changed)
        # connect icon click event
        self._search_entry.connect("icon-release",
            self._search_icon_release)
        self._view.show()

    def clear(self):
        self._rigo_sm.change_view_state(
            Rigo.STATIC_VIEW_STATE)
        self._store.clear()
        ApplicationMetadata.discard()

    def append(self, opaque):
        self._store.append([opaque])
        self._rigo_sm.change_view_state(
            Rigo.BROWSER_VIEW_STATE)

    def append_many(self, opaque_list):
        for opaque in opaque_list:
            self._store.append([opaque])
        self._rigo_sm.change_view_state(
            Rigo.BROWSER_VIEW_STATE)

    def clear_safe(self):
        ApplicationMetadata.discard()
        self._rigo_sm.change_view_state_safe(
            Rigo.STATIC_VIEW_STATE)
        GLib.idle_add(self._store.clear)

    def append_safe(self, opaque):
        GLib.idle_add(self.append, opaque)
        self._rigo_sm.change_view_state_safe(
            Rigo.BROWSER_VIEW_STATE)

    def append_many_safe(self, opaque_list):
        GLib.idle_add(self.append_many, opaque_list)
        self._rigo_sm.change_view_state_safe(
            Rigo.BROWSER_VIEW_STATE)

class WelcomeBox(Gtk.VBox):

    def __init__(self):
        Gtk.VBox.__init__(self)
        self._image_path = os.path.join(DATA_DIR, "ui/gtk3/art/rigo.png")

    def render(self):
        image = Gtk.Image.new_from_file(self._image_path)
        label = Gtk.Label()
        label.set_markup(_("<i>Browse <b>Applications</b> with ease</i>"))
        self.pack_start(image, False, False, 0)
        self.pack_start(label, False, False, 0)
        label.show()
        image.show()


class NotificationBox(Gtk.VBox):

    def __init__(self, message):
        Gtk.VBox.__init__(self)
        self._message = message

    def render(self):
        label = Gtk.Label()
        label.set_markup(self._message)
        self.pack_start(label, False, False, 0)
        label.show()


class NotificationController(object):

    def __init__(self, entropy_client, notification_box):
        self._entropy = entropy_client
        self._box = notification_box
        self._updates = None

    def setup(self):
        GLib.timeout_add(3000, self._calculate_updates)

    def _calculate_updates(self):
        th = ParallelTask(self.__calculate_updates)
        th.daemon = True
        th.name = "CalculateUpdates"
        th.start()

    def __calculate_updates(self):
        updates, removal, fine, spm_fine = \
            self._entropy.calculate_updates()
        self._updates = updates
        GLib.idle_add(self._notify_updates_safe)

    def _notify_updates_safe(self):
        # FIXME, use ngettext here
        msg = _("There are <b>%d</b> updates available, want to <u>update now</u>?")
        msg = msg % (len(self._updates),)
        box = NotificationBox(msg)
        box.render()
        self._box.pack_start(box, False, False, False)
        box.show()
        self._box.show()


class Rigo(Gtk.Application):

    class RigoHandler:

        def onDeleteWindow(self, *args):
            while True:
                try:
                    entropy.tools.kill_threads()
                    Gtk.main_quit(*args)
                except KeyboardInterrupt:
                    continue
                break

    def __init__(self):
        self._builder = Gtk.Builder()
        self._builder.add_from_file(os.path.join(DATA_DIR, "ui/gtk3/rigo.ui"))
        self._builder.connect_signals(Rigo.RigoHandler())
        self._window = self._builder.get_object("window1")
        self._app_vbox = self._builder.get_object("appVbox")
        self._search_entry = self._builder.get_object("searchEntry")
        self._scrolled_view = self._builder.get_object("scrolledView")
        self._static_view = self._builder.get_object("staticViewVbox")
        icons = get_sc_icon_theme(DATA_DIR)
        self._view = AppTreeView(self._app_vbox, icons, True,
                                 AppListStore.ICON_SIZE, store=None)
        self._scrolled_view.add(self._view)

        self._notification = self._builder.get_object("notificationBox")
        self._welcome_box = WelcomeBox()

        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-error-bell", False)
        # wire up the css provider to reconfigure on theme-changes
        self._window.connect("style-updated",
                                 self._on_style_updated,
                                 init_sc_css_provider,
                                 settings,
                                 Gdk.Screen.get_default(),
                                 DATA_DIR)

        self._entropy = Client()
        self._entropy_ws = EntropyWebService(self._entropy)

        self._state_mutex = Lock()
        self._current_state = Rigo.STATIC_VIEW_STATE
        self._pvc = PackagesViewController(
            self._entropy, icons, self._entropy_ws,
            self, self._search_entry, self._view)
        self._nc = NotificationController(
            self._entropy, self._notification)

    BROWSER_VIEW_STATE = 1
    STATIC_VIEW_STATE = 2

    def change_view_state(self, state, child_widget=None):
        """
        Change Rigo Application UI state.
        You can pass a custom widget that will be shown in case
        of static view state.
        """
        with self._state_mutex:
            if state == Rigo.BROWSER_VIEW_STATE:
                self._static_view.set_visible(False)
                # release all the childrens of static_view
                for child in self._static_view.get_children():
                    self._static_view.remove(child)
                self._scrolled_view.set_visible(True)
                self._scrolled_view.show()

            elif state == Rigo.STATIC_VIEW_STATE:
                self._scrolled_view.set_visible(False)
                if child_widget is not None:
                    for child in self._static_view.get_children():
                        self._static_view.remove(child)
                    self._static_view.pack_start(child_widget,
                                                 False, False, 0)
                    child_widget.show()
                else:
                    # keep the current widget if any, or add the
                    # welcome widget
                    if not self._static_view.get_children():
                        self._welcome_box.show()
                        self._static_view.pack_start(self._welcome_box,
                                                     False, False, 0)

                self._static_view.set_visible(True)
                self._static_view.show()

            else:
                raise AttributeError("wrong view state")

            self._current_state = state

    def change_view_state_safe(self, state, child_widget=None):
        """
        Thread-safe version of change_view_state().
        """
        def _do_change():
            return self.change_view_state(state, child_widget=child_widget)
        GLib.idle_add(_do_change)

    def _on_style_updated(self, widget, init_css_callback, *args):
        init_css_callback(widget, *args)

    def _show_ok_dialog(self, parent, title, message):
        dlg = Gtk.MessageDialog(parent=parent,
                            type=Gtk.MessageType.INFO,
                            buttons=Gtk.ButtonsType.OK)
        dlg.set_markup(message)
        dlg.set_title(title)
        dlg.run()
        dlg.destroy()

    def _permissions_setup(self):
        if not entropy.tools.is_user_in_entropy_group():
            # otherwise the lock handling would potentially
            # fail.
            self._show_ok_dialog(
                None,
                _("Not authorized"),
                _("You are not authorized to run Rigo"))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        acquired = entropy.tools.acquire_entropy_locks(
            self._entropy, shared=True, max_tries=1)
        if not acquired:
            self._show_ok_dialog(
                None,
                _("Rigo"),
                _("Another Application Manager is active"))
            entropy.tools.kill_threads()
            Gtk.main_quit()
            return

        self._pvc.setup()
        self._nc.setup()
        self._window.show()

    def run(self):
        self._welcome_box.render()
        self.change_view_state(self._current_state)
        GLib.idle_add(self._permissions_setup)

        GLib.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()
        entropy.tools.kill_threads()

if __name__ == "__main__":
    app = Rigo()
    app.run()
