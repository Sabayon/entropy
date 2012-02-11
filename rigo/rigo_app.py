import os
import sys
import copy

sys.path.insert(0, "../lib")
sys.path.insert(1, "../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/lib")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/rigo")

from gi.repository import Gtk, Gdk, Gio, GLib, GObject

from rigo.paths import DATA_DIR
from rigo.enums import Icons
from rigo.models.application import Application, ApplicationMetadata
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme

from entropy.const import etpUi
from entropy.tools import kill_threads
from entropy.exceptions import RepositoryError
from entropy.client.interfaces import Client
from entropy.misc import TimeScheduled, ParallelTask
from entropy.i18n import _

etpUi['debug'] = True

class EntropyWebService(object):

    def __init__(self, entropy_client):
        self._entropy = entropy_client
        self._webserv_map = {}

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

        # with Privileges():
        try:
            webserv = self._get(self._entropy, repository_id)
        except WebService.UnsupportedService as err:
            webserv = None

        if webserv is None:
            self._webserv_map[repository_id] = -1
            # not available
            return

        try:
            available = webserv.service_available()
        except WebService.WebServiceException:
            available = False

        if not available:
            self._webserv_map[repository_id] = -1
            # not available
            return

        self._webserv_map[repository_id] = webserv
        return webserv

    def _get(self, entropy_client, repository_id, tx_cb = None):
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
        if tx_cb is not None:
            webserv._set_transfer_callback(tx_cb)
        return webserv


class AppListStore(Gtk.ListStore):

    # column types
    COL_TYPES = (GObject.TYPE_PYOBJECT,)

    # column id
    COL_ROW_DATA = 0

    # default icon size displayed in the treeview
    ICON_SIZE = 32

    def __init__(self, entropy_client, view, icons, icon_size=48):
        Gtk.ListStore.__init__(self)
        self._view = view
        self._entropy = entropy_client
        self._icons = icons
        self._icon_size = icon_size
        self._icon_cache = {}
        self._missing_icon = self._icons.load_icon(
            Icons.MISSING_APP, icon_size, 0)
        self.set_column_types(self.COL_TYPES)

        # Startup Entropy Package Metadata daemon
        ApplicationMetadata.start()

    def _ui_redraw_callback(self, *args):
        GLib.idle_add(self._view.queue_draw)

    def get_icon(self, pkg_match):
        # FIXME, parallel load from UGC?
        # or run UGC on separate task?
        app = Application(self._entropy, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        name = app.name
        icon = self._icon_cache.get(name)
        if icon == -1:
            # icon not available
            return self._missing_icon
        if icon is not None:
            return icon

        if self._icons.has_icon(name):
            try:
                icon = self._icons.load_icon(
                    name, self._icon_size, 0)
            except (Gio.Error, GObject.GError):
                # no such file or directory (gio.Error)
                # unrecognized file format (gobject.GError)
                icon = None
            if icon:
                self._icon_cache[name] = icon
            else:
                self._icon_cache[name] = -1
                icon = self._missing_icon
        else:
            self._icon_cache[name] = -1
            icon = self._missing_icon
        return icon

    def is_installed(self, pkg_match):
        app = Application(self._entropy, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app.is_installed()

    def get_markup(self, pkg_match):
        app = Application(self._entropy, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app.get_markup()

    def get_review_stats(self, pkg_match):
        app = Application(self._entropy, pkg_match,
                          redraw_callback=self._ui_redraw_callback)
        return app.get_review_stats()

    def get_transaction_progress(self, pkg_match):
        # TODO: complete
        # int from 0 - 100, or -1 for no transaction
        return -1


class PackagesViewController(object):

    def __init__(self, entropy_client, icons, entropy_ws, search_entry, view):
        self._entropy = entropy_client
        self._icons = icons
        self._entropy_ws = entropy_ws
        self._search_entry = search_entry
        self._view = view

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
        self._store = AppListStore(self._entropy, self._view,
                                   self._icons)
        #Gtk.ListStore(GObject.TYPE_PYOBJECT)
        self._view.set_model(self._store)

        # setup searchEntry event
        self._search_entry.connect(
            "changed", self._search_changed)
        self._view.show()

    def clear(self):
        self._store.clear()
        ApplicationMetadata.discard()

    def append(self, opaque):
        self._store.append([opaque])

    def append_many(self, opaque_list):
        for opaque in opaque_list:
            self._store.append([opaque])

    def clear_safe(self):
        ApplicationMetadata.discard()
        GLib.idle_add(self._store.clear)

    def append_safe(self, opaque):
        GLib.idle_add(self.append, opaque)

    def append_many_safe(self, opaque_list):
        GLib.idle_add(self.append_many, opaque_list)


class NotificationBox(Gtk.VBox):

    def __init__(self, message):
        Gtk.VBox.__init__(self)
        self._message = message

    def render(self):
        label = Gtk.Label()
        label.set_markup(self._message)
        self.pack_start(label, False, False, False)
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
            Gtk.main_quit(*args)


    def __init__(self):
        self._builder = Gtk.Builder()
        self._builder.add_from_file(os.path.join(DATA_DIR, "ui/gtk3/rigo.ui"))
        self._builder.connect_signals(Rigo.RigoHandler())
        self._window = self._builder.get_object("window1")
        self._app_vbox = self._builder.get_object("appVbox")
        self._search_entry = self._builder.get_object("searchEntry")
        self._scrolled_view = self._builder.get_object("scrolledView")
        icons = get_sc_icon_theme(DATA_DIR)
        self._view = AppTreeView(self._app_vbox, icons, True, store=None)
        self._scrolled_view.add(self._view)
        self._notification = self._builder.get_object("notificationBox")

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
        # FIXME, lxnay locking

        self._entropy_ws = EntropyWebService(self._entropy)

        # Setup Packages View Controller class
        self._pvc = PackagesViewController(
            self._entropy, icons, self._entropy_ws,
            self._search_entry, self._view)
        self._nc = NotificationController(
            self._entropy, self._notification)

    def _on_style_updated(self, widget, init_css_callback, *args):
        init_css_callback(widget, *args)

    def run(self):
        self._pvc.setup()
        self._nc.setup()
        self._window.show()

        GLib.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()
        kill_threads()

if __name__ == "__main__":
    app = Rigo()
    app.run()
