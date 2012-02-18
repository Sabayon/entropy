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
from rigo.entropyapi import EntropyWebService
from rigo.models.application import Application, ApplicationMetadata
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    RepositoriesUpdateNotificationBox, UpdatesNotificationBox
from rigo.ui.gtk3.widgets.welcome import WelcomeBox
from rigo.ui.gtk3.models.appliststore import AppListStore
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme

from entropy.const import etpUi, const_debug_write, const_debug_enabled
from entropy.client.interfaces import Client
from entropy.client.interfaces.repository import Repository
from entropy.misc import TimeScheduled, ParallelTask
from entropy.i18n import _, ngettext

import entropy.tools


class ApplicationViewController(GObject.Object):

    __gsignals__ = {
        # View has been cleared
        "view-cleared" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
        # View has been filled
        "view-filled" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
    }

    def __init__(self, entropy_client, icons, entropy_ws,
                 search_entry, view):
        GObject.Object.__init__(self)
        self._entropy = entropy_client
        self._icons = icons
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
        self.set_many_safe(matches)

    def setup(self):
        self._store = AppListStore(
            self._entropy, self._entropy_ws,
            self._view, self._icons)
        self._view.set_model(self._store)

        self._search_entry.connect(
            "changed", self._search_changed)
        self._search_entry.connect("icon-release",
            self._search_icon_release)
        self._view.show()

    def clear(self):
        self._store.clear()
        ApplicationMetadata.discard()
        if const_debug_enabled():
            const_debug_write(__name__, "AVC: emitting view-cleared")
        self.emit("view-cleared")

    def append(self, opaque):
        self._store.append([opaque])
        if const_debug_enabled():
            const_debug_write(__name__, "AVC: emitting view-filled")
        self.emit("view-filled")

    def append_many(self, opaque_list):
        for opaque in opaque_list:
            self._store.append([opaque])
        if const_debug_enabled():
            const_debug_write(__name__, "AVC: emitting view-filled")
        self.emit("view-filled")

    def set_many(self, opaque_list):
        self._store.clear()
        ApplicationMetadata.discard()
        return self.append_many(opaque_list)

    def clear_safe(self):
        GLib.idle_add(self.clear)

    def append_safe(self, opaque):
        GLib.idle_add(self.append, opaque)

    def append_many_safe(self, opaque_list):
        GLib.idle_add(self.append_many, opaque_list)

    def set_many_safe(self, opaque_list):
        GLib.idle_add(self.set_many, opaque_list)


class NotificationController(GObject.Object):

    """
    Notification area widget controller code.
    """

    def __init__(self, entropy_client, avc, notification_box):
        GObject.Object.__init__(self)
        self._entropy = entropy_client
        self._avc = avc
        self._box = notification_box
        self._updates = None
        self._security_updates = None

    def setup(self):
        GLib.timeout_add(3000, self._calculate_updates)

    def _calculate_updates(self):
        th = ParallelTask(self.__calculate_updates)
        th.daemon = True
        th.name = "CalculateUpdates"
        th.start()

    def __calculate_updates(self):
        if Repository.are_repositories_old():
            GLib.idle_add(self._notify_old_repositories_safe)
            return

        updates, removal, fine, spm_fine = \
            self._entropy.calculate_updates()
        self._updates = updates
        self._security_updates = self._entropy.calculate_security_updates()
        GLib.idle_add(self._notify_updates_safe)

    def _notify_updates_safe(self):
        """
        Add NotificationBox signaling the user that updates
        are available.
        """
        updates_len = len(self._updates)
        if updates_len == 0:
            # no updates, do not show anything
            return

        box = UpdatesNotificationBox(
            self._entropy, self._avc,
            updates_len, len(self._security_updates))
        box.connect("upgrade-request", self._on_upgrade)
        box.connect("show-request", self._on_update_show)
        self.append(box)

    def _notify_old_repositories_safe(self):
        """
        Add NotificationBox signaling the user that repositories
        are old..
        """
        box = RepositoriesUpdateNotificationBox(
            self._entropy, self._avc)
        box.connect("update-request", self._on_update)
        self.append(box)

    def _on_upgrade(self, *args):
        # FIXME, lxnay complete
        print("On Upgrade Request Received", args)

    def _on_update(self, *args):
        # FIXME, lxnay complete
        print("On Update Request Received", args)

    def _on_update_show(self, *args):
        self._avc.set_many_safe(self._updates)

    def append(self, box, timeout=None):
        """
        Append a notification to the Notification area.
        """
        box.render()
        self._box.pack_start(box, False, False, 0)
        box.show()
        self._box.show()
        if timeout is not None:
            GLib.timeout_add_seconds(timeout, self.remove, box)

    def append_safe(self, box, timeout=None):
        """
        Thread-safe version of append().
        """
        def _append():
            self.append(box, timeout=timeout)
        GLib.idle_add(_append)

    def remove(self, box):
        """
        Remove a NotificationBox from this notification
        area, if there.
        """
        if box in self._box.get_children():
            self._box.remove(box)
            box.destroy()

    def remove_safe(self, box):
        """
        Thread-safe version of remove().
        """
        GLib.idle_add(self.remove, box)

    def clear(self):
        """
        Clear all the notifications.
        """
        for child in self._box.get_children():
            self._box.remove(child)
            child.destroy()

    def clear_safe(self):
        """
        Thread-safe version of clear().
        """
        GLib.idle_add(self.clear)


class ApplicationView(Gtk.VBox):
    """
    Applications View Container, exposing all the events
    that can happen to Applications listed in the contained
    TreeView.
    """

    __gsignals__ = {
        # Double click on application widget
        "application-activated" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        # Single click on application widget
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        # action requested for application
        "application-request-action" : (GObject.SignalFlags.RUN_LAST,
                                        None,
                                        (GObject.TYPE_PYOBJECT,
                                         GObject.TYPE_PYOBJECT,
                                         GObject.TYPE_PYOBJECT,
                                         str),
                                       ),
    }

    def __init__(self):
        Gtk.VBox.__init__(self)

    def setup(self):
        """
        Setup ApplicationView signals, etc.
        """
        for child in self.get_children():
            child.show()


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
        self._entropy = Client()
        self._entropy_ws = EntropyWebService(self._entropy)

        self._builder = Gtk.Builder()
        self._builder.add_from_file(os.path.join(DATA_DIR, "ui/gtk3/rigo.ui"))
        self._builder.connect_signals(Rigo.RigoHandler())
        self._window = self._builder.get_object("rigoWindow")
        self._app_vbox = self._builder.get_object("appViewVbox")
        self._search_entry = self._builder.get_object("searchEntry")
        self._static_view = self._builder.get_object("staticViewVbox")
        self._notification = self._builder.get_object("notificationBox")

        self._scrolled_view = Gtk.ScrolledWindow()
        self._scrolled_view.set_policy(Gtk.PolicyType.NEVER,
                                       Gtk.PolicyType.AUTOMATIC)

        self._app_view = ApplicationView()
        self._app_view.add(self._scrolled_view)
        self._app_vbox.pack_start(self._app_view, True, True, 0)

        icons = get_sc_icon_theme(DATA_DIR)
        self._view = AppTreeView(self._app_view, icons, True,
                                 AppListStore.ICON_SIZE, store=None)
        self._scrolled_view.add(self._view)

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

        self._current_state = Rigo.STATIC_VIEW_STATE
        self._state_transactions = {
            Rigo.BROWSER_VIEW_STATE: (
                self._enter_browser_state,
                self._exit_browser_state),
            Rigo.STATIC_VIEW_STATE: (
                self._enter_static_state,
                self._exit_static_state),
        }
        self._state_mutex = Lock()
        self._avc = ApplicationViewController(
            self._entropy, icons, self._entropy_ws,
            self._search_entry, self._view)

        self._avc.connect("view-cleared", self._on_view_cleared)
        self._avc.connect("view-filled", self._on_view_filled)

        self._nc = NotificationController(
            self._entropy, self._avc, self._notification)

    def _on_view_cleared(self, *args):
        self.change_view_state(Rigo.STATIC_VIEW_STATE)

    def _on_view_filled(self, *args):
        self.change_view_state(Rigo.BROWSER_VIEW_STATE)

    # Possible Rigo Application UI States
    BROWSER_VIEW_STATE, STATIC_VIEW_STATE = range(2)

    def _exit_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._app_view.hide()

    def _enter_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._app_view.show()
        self._current_state = Rigo.BROWSER_VIEW_STATE

    def _exit_static_state(self):
        """
        Action triggered when UI exits the Static Browser
        state (or mode). AKA the Welcome Box.
        """
        self._static_view.hide()
        # release all the childrens of static_view
        for child in self._static_view.get_children():
            self._static_view.remove(child)

    def _enter_static_state(self):
        """
        Action triggered when UI exits the Static Browser
        state (or mode). AKA the Welcome Box.
        """
        # keep the current widget if any, or add the
        # welcome widget
        if not self._static_view.get_children():
            self._welcome_box.show()
            self._static_view.pack_start(self._welcome_box,
                                         False, False, 0)
        self._static_view.show()
        self._current_state = Rigo.STATIC_VIEW_STATE

    def change_view_state(self, state):
        """
        Change Rigo Application UI state.
        You can pass a custom widget that will be shown in case
        of static view state.
        """
        with self._state_mutex:
            txc = self._state_transactions.get(
                state)
            if txc is None:
                raise AttributeError("wrong view state")
            enter_st, exit_st = txc

            current_enter_st, current_exit_st = self._state_transactions.get(
                self._current_state)
            # exit from current state
            current_exit_st()
            # enter the new state
            enter_st()

    def change_view_state_safe(self, state):
        """
        Thread-safe version of change_view_state().
        """
        def _do_change():
            return self.change_view_state(state)
        GLib.idle_add(_do_change)

    def _on_style_updated(self, widget, init_css_callback, *args):
        """
        Gtk Style callback, nothing to see here.
        """
        init_css_callback(widget, *args)

    def _show_ok_dialog(self, parent, title, message):
        """
        Show ugly OK dialog window.
        """
        dlg = Gtk.MessageDialog(parent=parent,
                            type=Gtk.MessageType.INFO,
                            buttons=Gtk.ButtonsType.OK)
        dlg.set_markup(message)
        dlg.set_title(title)
        dlg.run()
        dlg.destroy()

    def _permissions_setup(self):
        """
        Check execution privileges and spawn the Rigo UI.
        """
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

        self._app_view.setup()
        self._avc.setup()
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
