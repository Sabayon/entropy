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
import subprocess
import time
from threading import Timer, Semaphore, Lock

from gi.repository import Gtk, GLib, GObject, Pango

from rigo.em import StockEms
from rigo.utils import build_register_url, open_url, escape_markup, \
    prepare_markup
from rigo.models.application import Application
from rigo.enums import AppActions, LocalActivityStates, RigoViewStates

from entropy.const import etpConst, const_convert_to_unicode, \
    const_debug_write, const_mkstemp
from entropy.i18n import _, ngettext
from entropy.services.client import WebService
from entropy.misc import ParallelTask, TimeScheduled

import entropy.tools

class NotificationBox(Gtk.HBox):

    """
    Generic notification widget to be used in the
    Rigo notification area.
    """

    def __init__(self, message, message_widget=None,
                 message_type=None, tooltip=None,
                 context_id=None):
        Gtk.HBox.__init__(self)
        self._message = message
        # if not None, it will replace Gtk.Label(self._message)
        self._message_widget = message_widget
        self._buttons = []
        self._widgets = []
        self._type = message_type
        if self._type is None:
            self._type = Gtk.MessageType.INFO
        self._tooltip = tooltip
        self._context_id = context_id

    def add_button(self, text, clicked_callback):
        """
        Add a Gtk.Button() to this container.
        Return the newly created Gtk.Button().
        """
        button = Gtk.Button(label=text)
        button.set_use_underline(True)
        button.connect("clicked", clicked_callback)
        self._buttons.append(button)
        return button

    def add_widget(self, widget):
        """
        Add Gtk.Widget to the Buttons Area on the right.
        """
        self._widgets.append(widget)

    def add_destroy_button(self, text, callback=None):
        """
        Add button that destroys the whole Notification object.
        It is possible to provide a callback function that will be called
        without arguments before destroying the notification box.
        """
        def _destroy(*args):
            if callback is not None:
                callback()
            self.destroy()
        self.add_button(text, _destroy)

    def render(self):
        """
        Render the Notification box filling in the container.
        """
        bar = Gtk.InfoBar()
        if self._tooltip is not None:
            bar.set_tooltip_markup(self._tooltip)
        bar.set_message_type(self._type)

        content_area = bar.get_content_area()
        hbox = Gtk.HBox()

        message_hbox = Gtk.HBox()
        message_hbox.set_name("message-area")
        if self._message_widget is None:
            label = Gtk.Label()
            label.set_markup(self._message)
            label.set_line_wrap_mode(Pango.WrapMode.WORD)
            label.set_line_wrap(True)
            label.set_property("expand", True)
            label.set_alignment(0.02, 0.50)
            message_hbox.pack_start(label, True, True, 0)
        else:
            message_hbox.pack_start(self._message_widget, True, True, 0)
        hbox.pack_start(message_hbox, True, True, 0)

        button_align = Gtk.Alignment()
        button_align.set(1.0, 1.0, 0.0, 0.0)
        button_vbox = Gtk.VBox() # to avoid spanning in height
        button_align.add(button_vbox)
        button_hbox = Gtk.HBox()
        button_hbox.set_name("button-area")
        for button in self._buttons:
            button_hbox.pack_start(button, False, False, 3)
        for widget in self._widgets:
            button_hbox.pack_start(widget, False, False, 3)
        button_vbox.pack_start(button_hbox, False, False, 0)
        hbox.pack_start(button_align, False, False, 2)

        content_area.set_property("expand", False)
        content_area.set_property("hexpand", True)
        content_area.add(hbox)

        bar.show_all()
        bar.get_action_area().hide()
        self.pack_start(bar, True, True, 0)

    def get_context_id(self):
        """
        Multiple NotificationBox instances can
        share the same context_id. This information
        is useful when showing multiple notifications
        sharing the same context is unwanted.
        """
        return self._context_id

    def is_managed(self):
        """
        If this method returns True, the NotificationBox
        will not be destroyed by parent or controller
        if not explicitly requested.
        """
        return False


class UpdatesNotificationBox(NotificationBox):

    # class level variable that makes possible to turn
    # off the updates notification for the whole process
    # lifecycle.
    _snoozed = False

    __gsignals__ = {
        # Update button clicked
        "upgrade-request" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
        "show-request" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
    }

    def __init__(self, entropy_client, avc,
                 updates_len, security_updates_len):
        self._entropy = entropy_client
        self._avc = avc

        msg = ngettext("There is <b>%d</b> update",
                       "There are <b>%d</b> updates",
                       updates_len)
        msg = msg % (updates_len,)

        if security_updates_len > 0:
            sec_msg = ", " + ngettext("and <b>%d</b> security update",
                                      "and <b>%d</b> security updates",
                                      security_updates_len)
            sec_msg = sec_msg % (security_updates_len,)
            msg += sec_msg

        msg += ". " + _("What to do?")

        NotificationBox.__init__(self, prepare_markup(msg),
            tooltip=prepare_markup(
                _("Updates available, how about installing them?")),
            message_type=Gtk.MessageType.WARNING,
            context_id="UpdatesNotificationBox")
        self.add_button(_("_Update"), self._update)
        self.add_button(_("_Show"), self._show)
        self.add_destroy_button(_("_Ignore"))
        self.add_destroy_button(_("Srsly, ignore!"),
                                callback=UpdatesNotificationBox.snooze)

    def _update(self, button):
        """
        Update button callback from the updates notification box.
        """
        self.emit("upgrade-request")

    def _show(self, button):
        """
        Show button callback from the updates notification box.
        """
        self.emit("show-request")

    @classmethod
    def snooze(cls):
        """
        Turn off this notification for the whole process lifetime.
        """
        cls._snoozed = True

    @classmethod
    def unsnooze(cls):
        """
        Turn back on this notification.
        """
        cls._snoozed = False

    @classmethod
    def snoozed(cls):
        """
        Return whether the notification is currently "snoozed".
        """
        return cls._snoozed


class RepositoriesUpdateNotificationBox(NotificationBox):

    __gsignals__ = {
        # Update button clicked
        "update-request" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
    }

    def __init__(self, entropy_client, avc, unavailable=None):
        self._entropy = entropy_client
        self._avc = avc

        if unavailable is None:
            msg = _("The list of available Applications is old"
                    ", <b>update now</b>?")
        else:
            msg = _("Repositories should be downloaded, <b>update now</b>?")

        NotificationBox.__init__(self, msg,
            tooltip=prepare_markup(_("I dunno dude, I'd say Yes")),
            message_type=Gtk.MessageType.ERROR,
            context_id="RepositoriesUpdateNotificationBox")
        self.add_button(_("_Yes, why not?"), self._update)
        self.add_destroy_button(_("_No, thanks"))

    def _update(self, button):
        """
        Update button callback from the updates notification box.
        """
        self.emit("update-request")


class LoginNotificationBox(NotificationBox):

    """
    NotificationBox asking user to login to Entropy Web Service.
    """

    __gsignals__ = {
        # Emitted when login is successful
        "login-success" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT,),
                          ),
        # Emitted when login fails, not going
        # to retry anymore
        "login-failed" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          (GObject.TYPE_PYOBJECT,),
                          ),
    }

    def __init__(self, avc, entropy_ws, app, context_id=None):
        self._avc = avc
        self._entropy_ws = entropy_ws
        self._app = app
        self._repository_id = app.get_details().channelname
        if context_id is None:
            context_id = "LoginNotificationBox"

        NotificationBox.__init__(self, None,
            message_widget=self._make_login_box(),
            tooltip=prepare_markup(
                _("You need to login to Entropy Web Services")),
            message_type=Gtk.MessageType.WARNING,
            context_id=context_id)

        self.add_button(_("_Login"), self._login)
        self.add_button(_("Register"), self._register)

        def _destroy(*args):
            self.emit("login-failed", self._app)
            self.destroy()
        self.add_button(_("_Cancel"), _destroy)

    def _make_login_box(self):

        vbox = Gtk.VBox()

        hbox = Gtk.HBox()

        username_box = Gtk.VBox()
        username_label = Gtk.Label()
        username_label.set_markup("<small>" + \
            escape_markup(_("Username")) + "</small>")
        username_label.set_alignment(0.0, 0.50)
        username_box.pack_start(username_label, False, False, 0)
        self._username_entry = Gtk.Entry()
        username_box.pack_start(self._username_entry, False, False, 0)
        hbox.pack_start(username_box, False, False, 0)

        password_box = Gtk.VBox()
        password_label = Gtk.Label()
        password_label.set_markup("<small>" + \
            escape_markup(_("Password")) + "</small>")
        password_label.set_alignment(0.0, 0.50)
        password_box.pack_start(password_label, False, False, 0)
        self._password_entry = Gtk.Entry()
        self._password_entry.set_visibility(False)
        password_box.pack_start(self._password_entry, False, False, 0)
        hbox.pack_start(password_box, True, False, 0)

        hbox.set_property("expand", True)

        vbox.pack_start(hbox, False, False, 0)
        self._login_message = Gtk.Label()
        self._login_message.set_no_show_all(True)
        self._login_message.set_alignment(0.0, 1.0)
        self._login_message.set_padding(-1, 8)
        self._login_message.set_name("message-area-error")
        vbox.pack_start(self._login_message, False, False, 0)

        return vbox

    def _login_thread_body(self, username, password):
        """
        Execute the actual login procedure.
        """
        webserv = self._entropy_ws.get(self._repository_id)
        if webserv is None:
            # can't be, if we're here, this is already not None
            return

        def _login_error():
            self._login_message.show()
            self._login_message.set_markup(
                prepare_markup(
                    _("Login <b>error</b>!")))

        webserv.add_credentials(username, password)
        try:
            webserv.validate_credentials()
        except WebService.MethodNotAvailable:
            GLib.idle_add(_login_error)
            return
        except WebService.AuthenticationFailed:
            webserv.remove_credentials()
            GLib.idle_add(_login_error)
            return

        def _emit_success():
            self.emit("login-success", username, self._app)
            self._avc.emit("logged-in", username)
            GLib.idle_add(self.destroy)
        GLib.idle_add(_emit_success)

    def _login(self, button):
        """
        Try to login to Entropy Web Services.
        """
        username = self._username_entry.get_text()
        password = self._password_entry.get_text()

        try:
            username = const_convert_to_unicode(
                username, enctype=etpConst['conf_encoding'])
            password = const_convert_to_unicode(
                password, enctype=etpConst['conf_encoding'])
        except UnicodeDecodeError as err:
            const_debug_write(
                __name__,
                "LoginNotificationBox._login: %s" % (repr(err),))
            return

        task = ParallelTask(
            self._login_thread_body, username, password)
        task.name = "LoginNotificationThreadBody"
        task.daemon = True
        task.start()

    def _register(self, button):
        """
        Register button click event.
        """
        open_url(build_register_url())


class ConnectivityNotificationBox(NotificationBox):

    def __init__(self):

        msg = _("Cannot connect to Entropy Web Services, "
                "are you connected to the <b>interweb</b>?")

        NotificationBox.__init__(self, msg,
            tooltip=prepare_markup(_("Don't ask me...")),
            message_type=Gtk.MessageType.ERROR,
            context_id="ConnectivityNotificationBox")
        self.add_destroy_button(_("_Of course not"))


class PleaseWaitNotificationBox(NotificationBox):

    def __init__(self, message, context_id):

        NotificationBox.__init__(self, message,
            tooltip=prepare_markup(_("A watched pot never boils")),
            message_type=Gtk.MessageType.INFO,
            context_id=context_id)
        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(StockEms.XXLARGE, StockEms.XXLARGE)
        self.add_widget(self._spinner)

    def is_managed(self):
        """
        Reimplemented from NotificationBox.
        Please Wait Boxes are usually managed.
        """
        return True

    def render(self):
        """
        Reimplemented from NotificationBox.
        Start the Please Wait Spinner.
        """
        NotificationBox.render(self)
        self._spinner.start()


class LicensesNotificationBox(NotificationBox):

    __gsignals__ = {
        # Licenses have been accepted
        "accepted" : (GObject.SignalFlags.RUN_LAST,
                      None,
                      (GObject.TYPE_PYOBJECT,),
                      ),
        # Licenses have been declined
        "declined" : (GObject.SignalFlags.RUN_LAST,
                      None,
                      tuple(),
                      ),
    }

    def __init__(self, app, entropy_client, license_map):

        """
        LicensesNotificationBox constructor.

        @param entropy_client: Entropy Client object
        @param license_map: mapping composed by license id as key and
        list of Application objects as value.
        """
        self._app = app
        self._entropy = entropy_client
        self._licenses = license_map

        licenses = sorted(license_map.keys(),
                          key = lambda x: x.lower())
        lic_txts = []
        for lic in licenses:
            lic_txt = "<a href=\"%s\">%s</a>" % (lic, lic,)
            lic_txts.append(lic_txt)

        if app is None:
            msg = _("You are required to <b>review</b> and <b>accept</b>"
                    " the following licenses before continuing: %s")
            msg = msg % (", ".join(lic_txts),)
            msg = prepare_markup(msg)
        else:
            msg = _("<b>%s</b> Application or one of its "
                    "dependencies is distributed with the following"
                    " licenses: %s")
            msg = msg % (self._app.name, ", ".join(lic_txts),)
            msg = prepare_markup(msg)

        label = Gtk.Label()
        label.set_markup(prepare_markup(msg))
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_line_wrap(True)
        label.set_property("expand", True)
        label.set_alignment(0.02, 0.50)
        label.connect("activate-link",
                      self._on_license_activate)

        NotificationBox.__init__(
            self, None, message_widget=label,
            tooltip=prepare_markup(
                _("Make sure to review all the licenses")),
            message_type=Gtk.MessageType.WARNING,
            context_id="LicensesNotificationBox")

        self.add_button(_("Accept"), self._on_accept)
        self.add_button(_("Accept forever"),
                        self._on_accept_forever)
        self.add_button(_("Decline"),
                        self._on_decline)

    def _on_accept(self, widget):
        """
        Licenses have been accepted.
        """
        self.emit("accepted", False)

    def _on_accept_forever(self, widget):
        """
        Licenses have been forever accepted.
        """
        self.emit("accepted", True)

    def _on_decline(self, widget):
        """
        Licenses have been declined.
        """
        self.emit("declined")

    def _show_license(self, uri, license_apps):
        """
        Show selected License to User.
        """
        tmp_fd, tmp_path = None, None
        try:

            license_text = None
            # get the first repo with valid license text
            repos = set([x.get_details().channelname for \
                             x in license_apps])
            if not repos:
                return

            with self._entropy.rwsem().reader():
                for repo_id in repos:
                    repo = self._entropy.open_repository(repo_id)
                    license_text = repo.retrieveLicenseText(uri)
                    if license_text is not None:
                        break

            if license_text is not None:
                tmp_fd, tmp_path = const_mkstemp(suffix=".txt")
                try:
                    license_text = const_convert_to_unicode(
                        license_text, enctype=etpConst['conf_encoding'])
                except UnicodeDecodeError:
                    license_text = const_convert_to_unicode(
                        license_text)

                with entropy.tools.codecs_fdopen(
                    tmp_fd, "w", etpConst['conf_encoding']) as tmp_f:
                    tmp_f.write("License: %s\n" % (
                            uri,))
                    apps = self._licenses.get(uri, [])
                    if apps:
                        tmp_f.write("Applications:\n")
                    for app in apps:
                        tmp_f.write("\t%s\n" % (app.name,))
                    if apps:
                        tmp_f.write("\n")
                    tmp_f.write("-" * 79 + "\n")
                    tmp_f.write(license_text)
                    tmp_f.flush()
            else:
                const_debug_write(
                    __name__,
                    "LicensesNotificationBox._show_license: "
                    "not available"
                    )
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            # leaks, but xdg-open is async

        if tmp_path is not None:
            open_url(tmp_path)

    def _on_license_activate(self, widget, uri):
        """
        License link clicked.
        """
        license_apps = self._licenses.get(uri)
        if not license_apps:
            return True
        task = ParallelTask(self._show_license, uri, license_apps)
        task.name = "ShowLicense"
        task.daemon = True
        task.start()
        return True


class OrphanedAppsNotificationBox(NotificationBox):

    def __init__(self, apc, rigo_service, entropy_client,
                 entropy_ws, manual_apps, apps):

        self._apc = apc
        self._service = rigo_service
        self._apps = apps
        self._manual_apps = manual_apps
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws

        self._label = Gtk.Label()
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_line_wrap(True)
        self._label.set_property("expand", True)
        self._label.set_alignment(0.02, 0.50)
        self._setup_label(self._label)
        self._label.connect("activate-link", self._on_app_activate)

        NotificationBox.__init__(
            self, None, message_widget=self._label,
            message_type=Gtk.MessageType.INFO,
            context_id="OrphanedAppsNotificationBox")

        #if apps:
        #    self.add_button(_("Remove safe"), self._on_remove_safe)
        #self.add_button(_("Remove All"), self._on_remove_all)
        self.add_destroy_button(_("Close"))

        self._service.connect(
            "applications-managed",
            self._on_applications_managed)

    def is_managed(self):
        """
        This NotificationBox cannot be destroyed easily.
        """
        return True

    def _setup_label(self, label):
        """
        Setup message Label content.
        """
        msg = prepare_markup(
            _("Several <b>Applications</b>, no longer maintained by this "
              "distribution, have been found on your <b>System</b>. "
              "Some of them might require <b>manual review</b> before "
              "being uninstalled. Click on the Apps to expand."))
        msg += "\n"

        if self._manual_apps:
            msg += "\n%s: %s" % (
                prepare_markup(_("Manual review")),
                self._build_app_str_list(self._manual_apps),)
        if self._apps:
            msg += "\n%s: %s" % (
                prepare_markup(_("Safe to drop")),
                self._build_app_str_list(self._apps),)

        label.set_markup(prepare_markup(msg))

    def _build_app_str_list(self, apps):
        app_lst = []
        for app in apps:
            app_name = escape_markup(app.name)
            pkg_id, pkg_repo = app.get_details().pkg
            app_str = "<b><a href=\"%d|%s\">%s</a></b>" % (
                pkg_id, pkg_repo, app_name)
            app_lst.append(app_str)
        return prepare_markup("<small>" + \
                              ", ".join(app_lst) + "</small>")

    def _on_remove_safe(self, widget):
        """
        "Remove safe" button click event.
        """
        for app in self._apps:
            self._apc.emit(
                "application-request-action",
                app, AppActions.REMOVE)

    def _on_remove_all(self, widget):
        """
        "Remove All" button click event.
        """
        pkg_cache = set()
        for app in self._apps + self._manual_apps:
            pkg = app.get_details().pkg
            if pkg in pkg_cache:
                continue
            pkg_cache.add(pkg)
            self._apc.emit(
                "application-request-action",
                app, AppActions.REMOVE)

    def _on_applications_managed(self, widget, success, local_activity):
        """
        Reload Gtk.Label and drop removed apps.
        """
        if not success:
            return
        if local_activity != LocalActivityStates.MANAGING_APPLICATIONS:
            return
        apps = [x for x in self._apps if x.is_available()]
        manual_apps = [x for x in self._manual_apps if x.is_available()]
        if not (apps or manual_apps):
            self.destroy()
            return
        self._apps = apps
        self._manual_apps = manual_apps
        self._setup_label(self._label)

    def _on_app_activate(self, widget, uri):
        """
        Application clickable Label event.
        """
        pkg_id, pkg_repo = uri.split("|", 1)
        pkg_id = int(pkg_id)
        app = Application(
            self._entropy, self._entropy_ws,
            self._service, (pkg_id, pkg_repo))
        self._apc.emit("application-activated", app)
        return True


class InstallNotificationBox(NotificationBox):

    __gsignals__ = {
        # Licenses have been accepted
        "accepted" : (GObject.SignalFlags.RUN_LAST,
                      None,
                      tuple(),
                      ),
        # Licenses have been declined
        "declined" : (GObject.SignalFlags.RUN_LAST,
                      None,
                      tuple(),
                      ),
    }

    def __init__(self, apc, avc, app, entropy_client, entropy_ws,
                 rigo_service, install, _message=None):
        """
        InstallNotificationBox constructor.

        @param entropy_client: Entropy Client object
        @param install: Application Install queue
        """
        self._apc = apc
        self._avc = avc
        self._app = app
        self._entropy_ws = entropy_ws
        self._entropy = entropy_client
        self._service = rigo_service
        self._install = sorted(
            install, key = lambda x: x.name)

        if _message is None:
            msg = prepare_markup(
                _("<b>%s</b> Application requires the installation "
                  "of the following Applications: %s"))
        else:
            msg = _message
        if len(self._install) <= 20:
            app_txts = []
            for _app in self._install:
                _pkg_id, _repo_id = _app.get_details().pkg
                app_txt = "<a href=\"%d|%s\">%s</a>" % (
                    _pkg_id, _repo_id, _app.name,)
                app_txts.append(app_txt)
            txt = ", ".join(app_txts)
        else:
            txt = "<a href=\"%s\">%s</a>" % (
                "full", _("Show full list"))

        msg = msg % (self._app.name, prepare_markup(txt),)

        label = Gtk.Label()
        label.set_markup(msg)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_line_wrap(True)
        label.set_property("expand", True)
        label.set_alignment(0.02, 0.50)
        label.connect("activate-link", self._on_app_activate)

        NotificationBox.__init__(
            self, None, message_widget=label,
            message_type=Gtk.MessageType.WARNING,
            context_id="InstallNotificationBox")

        self.add_button(_("Accept"), self._on_accept)
        self.add_button(_("Decline"), self._on_decline)

    def _on_accept(self, widget):
        """
        Licenses have been accepted.
        """
        self.emit("accepted")

    def _on_decline(self, widget):
        """
        Licenses have been declined.
        """
        self.emit("declined")

    def is_managed(self):
        """
        This NotificationBox cannot be destroyed easily.
        """
        return True

    def _on_app_activate(self, widget, uri):
        """
        License link clicked.
        """
        if uri == "full":
            self._avc.set_many(
                [x.get_details().pkg for x in self._install])
            return True
        pkg_id, pkg_repo = uri.split("|", 1)
        pkg_id = int(pkg_id)
        app = Application(
            self._entropy, self._entropy_ws,
            self._service, (pkg_id, pkg_repo))
        self._apc.emit("application-activated", app)
        return True


class RemovalNotificationBox(InstallNotificationBox):

    def __init__(self, apc, avc, app, entropy_client, entropy_ws,
                 rigo_service, removal):
        message = prepare_markup(
                _("<b>%s</b> Application requires the removal "
                  "of the following Applications: %s"))
        InstallNotificationBox.__init__(
            self, apc, avc, app, entropy_client,
            entropy_ws, rigo_service, removal, _message=message)


class QueueActionNotificationBox(NotificationBox):

    TIMER_SECONDS = 10.0

    def __init__(self, app, daemon_action, callback, undo_callback,
                 undo_outcome):
        self._app = app
        self._action = daemon_action
        self._undo_outcome = undo_outcome

        self._callback_mutex = Lock()
        self._callback_called = False
        self._callback_sync_sem = Semaphore(0)
        self._callback_outcome = None
        self._callback = callback
        self._undo_callback = undo_callback

        self._update_timer_elapsed = 0.0
        self._update_timer_refresh = 0.5
        self._update_timer = TimeScheduled(
            self._update_timer_refresh,
            self._update_countdown_wrapper)
        self._update_timer.set_delay_before(True)
        self._update_timer.daemon = True
        self._update_timer.name = "QueueActionNotificationBoxUpdateTimer"

        self._timer = Timer(self.TIMER_SECONDS + 1, self._callback_wrapper)
        self._action_label = Gtk.Label()
        self._action_label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._action_label.set_line_wrap(True)
        self._action_label.set_property("expand", True)
        self._action_label.set_alignment(0.02, 0.50)
        self._update_countdown(int(self.TIMER_SECONDS))

        pkg = self._app.get_details().pkg
        context_id = "QueueActionNotificationContextId-%s" % (
            pkg,)
        NotificationBox.__init__(
            self, None, message_widget=self._action_label,
            message_type=Gtk.MessageType.WARNING,
            context_id=context_id)

        self.add_button(_("Confirm"), self._on_confirm)
        self.add_button(_("Undo"), self._on_undo)

    def render(self):
        """
        Overridden from NotificationBox
        """
        outcome = NotificationBox.render(self)
        self._start_time = time.time()
        self._update_timer.start()
        self._timer.start()
        return outcome

    def destroy(self):
        """
        Overridden from NotificationBox
        """
        self._update_timer.kill()
        return NotificationBox.destroy(self)

    def acquire(self):
        """
        Acquire Callback outcome, when callback is eventually
        spawned.
        """
        self._callback_sync_sem.acquire()
        return self._callback_outcome

    def _callback_wrapper(self):
        """
        Wrapper method that spawns the callback and stores the
        outcome into _callback_outcome, releasing the Semaphore
        once done.
        """
        if self._callback_called:
            return

        with self._callback_mutex:
            if self._callback_called:
                return
            self._callback_outcome = self._callback()
            self._callback_called = True
            GLib.idle_add(self.destroy)
        self._callback_sync_sem.release()

    def _update_countdown_wrapper(self):
        """
        Wrapper function that is called every 0.5 seconds
        updating the countdown status.
        """
        self._update_timer_elapsed += self._update_timer_refresh
        remaining = self.TIMER_SECONDS - self._update_timer_elapsed
        if remaining < 0.1:
            self._update_timer.kill()
            return
        GLib.idle_add(self._update_countdown, int(remaining))

    def _update_countdown(self, seconds):
        """
        Update Countdown message.
        """
        msg = prepare_markup(
            ngettext("<b>%s</b> Application Action will start "
              "in <big><b>%d</b></big> second",
              "<b>%s</b> Application Action will start "
              "in <big><b>%d</b></big> seconds",
              seconds))
        msg = msg % (self._app.name, seconds,)
        self._action_label.set_markup(prepare_markup(msg))

    def _on_confirm(self, widget):
        """
        Action has been confirmed.
        """
        self._timer.cancel()
        self._update_timer.kill()
        self._callback_wrapper()

    def _on_undo(self, widget):
        """
        Action has been cancelled.
        """
        self._timer.cancel()
        self._update_timer.kill()

        if self._callback_called:
            return
        with self._callback_mutex:
            if self._callback_called:
                return
            self._callback_outcome = self._undo_outcome

            if self._undo_callback is not None:
                self._undo_callback()

            self._callback_called = True
            GLib.idle_add(self.destroy)

        self._callback_sync_sem.release()

    def is_managed(self):
        """
        This NotificationBox cannot be destroyed easily.
        """
        return True


class ConfigUpdatesNotificationBox(NotificationBox):

    def __init__(self, entropy_client, avc, updates_len):
        self._entropy = entropy_client
        self._avc = avc

        msg = ngettext("There is <b>%d</b> configuration file update",
                       "There are <b>%d</b> configuration file updates",
                       updates_len)
        msg = msg % (updates_len,)

        msg += ".\n\n<small>"
        msg += _("It is <b>extremely</b> important to"
                 " update these configuration files before"
                 " <b>rebooting</b> the System.")
        msg += "</small>"

        context_id = "ConfigUpdatesNotificationContextId"
        NotificationBox.__init__(
            self, prepare_markup(msg),
            message_type=Gtk.MessageType.WARNING,
            context_id=context_id)

        self.add_button(_("Let me see"), self._on_show_me)
        self.add_destroy_button(_("Happily ignore"))

    def _on_show_me(self, widget):
        """
        Show the proposed configuration file updates
        """
        self._avc.emit(
            "view-want-change",
            RigoViewStates.CONFUPDATES_VIEW_STATE,
            None)

    def is_managed(self):
        """
        This NotificationBox cannot be destroyed easily.
        """
        return True


class NoticeBoardNotificationBox(NotificationBox):

    __gsignals__ = {
        "let-me-see" : (GObject.SignalFlags.RUN_LAST,
                        None,
                        tuple(),
                        ),
        "stop-annoying" : (GObject.SignalFlags.RUN_LAST,
                           None,
                           tuple(),
                           ),
    }

    def __init__(self, avc, notices_len):

        msg = ngettext("There is <b>%d</b> notice from a repository",
                       "There are <b>%d</b> notices from repositories",
                       notices_len)
        msg = msg % (notices_len,)

        msg += ".\n\n<small>"
        msg += _("It is <b>extremely</b> important to"
                 " always read them.")
        msg += "</small>"

        context_id = "NoticeBoardNotificationContextId"
        NotificationBox.__init__(
            self, prepare_markup(msg),
            message_type=Gtk.MessageType.INFO,
            context_id=context_id)

        self.add_button(_("Let me see"), self._on_let_me_see)
        self.add_button(_("Stop annoying me"), self._on_stop_annoying)
        self.add_destroy_button(_("Close"))

    def _on_stop_annoying(self, widget):
        """
        Stop showing this notification box as long as there are no
        upstream updates.
        """
        self.emit("stop-annoying")

    def _on_let_me_see(self, widget):
        """
        Show the proposed configuration file updates
        """
        self.emit("let-me-see")

    def is_managed(self):
        """
        This NotificationBox cannot be destroyed easily.
        """
        return True


class RenameRepositoryNotificationBox(NotificationBox):

    """
    NotificationBox used to rename repositories.
    """

    __gsignals__ = {
        "renamed" : (GObject.SignalFlags.RUN_LAST,
                     None,
                     tuple(),
                     ),
        "cancelled" : (GObject.SignalFlags.RUN_LAST,
                       None,
                       tuple(),
                       ),
    }

    def __init__(self, repo_object, rigo_service):
        self._repo = repo_object
        self._service = rigo_service
        context_id = "RenameRepositoryNotificationBox"

        NotificationBox.__init__(self, None,
            message_widget=self._make_rename_box(),
            tooltip=prepare_markup(
                _("You are about to rename a Repository")),
            message_type=Gtk.MessageType.INFO,
            context_id=context_id)

        self.add_button(_("_Rename"), self._rename)

        def _destroy(*args):
            self.emit("cancelled")
            self.destroy()
        self.add_button(_("_Cancel"), _destroy)

    def _make_rename_box(self):

        vbox = Gtk.VBox()
        hbox = Gtk.HBox()

        repo_box = Gtk.VBox()
        repo_label = Gtk.Label()
        repo_label.set_markup(
            escape_markup(_("Repository name")))
        repo_label.set_alignment(0.0, 0.50)
        repo_label.set_padding(-1, 5)
        repo_box.pack_start(repo_label, False, False, 0)
        self._repo_entry = Gtk.Entry()
        self._repo_entry.set_text(self._repo.repository())
        repo_box.pack_start(self._repo_entry, False, False, 0)
        hbox.pack_start(repo_box, False, False, 0)

        hbox.set_property("expand", True)

        self._repo_message = Gtk.Label()
        self._repo_message.set_no_show_all(True)
        self._repo_message.set_alignment(0.0, 1.0)
        self._repo_message.set_padding(10, 5)
        self._repo_message.set_name("message-area-error")
        hbox.pack_start(self._repo_message, False, False, 0)

        vbox.pack_start(hbox, False, False, 0)

        return vbox

    def _rename(self, button):
        """
        Try to login to Entropy Web Services.
        """
        repository_id = self._repo_entry.get_text()
        valid = entropy.tools.validate_repository_id(repository_id)
        if not valid:
            self._repo_message.show()
            self._repo_message.set_markup(
                prepare_markup(
                    _("<b>Invalid</b> Repository name!")))
            return

        from_repository_id = self._repo.repository()
        renamed = self._service.rename_repository(
            from_repository_id, repository_id)
        if not renamed:
            self._repo_message.show()
            self._repo_message.set_markup(
                prepare_markup(
                    _("Repository rename <b>not allowed</b>!")))
            return

        self.destroy()
        self.emit("renamed")


class PreservedLibsNotificationBox(NotificationBox):

    __gsignals__ = {
        # Update button clicked
        "upgrade-request" : (GObject.SignalFlags.RUN_LAST,
                          None,
                          tuple(),
                          ),
    }

    def __init__(self, preserved):

        preserved_len = len(preserved)
        msg = ngettext("There is <b>%d</b> preserved library on the system",
                       "There are <b>%d</b> preserved libraries on the system",
                       preserved_len)
        msg = msg % (preserved_len,)

        msg += ". " + _("What to do?")

        NotificationBox.__init__(
            self, prepare_markup(msg),
            tooltip=prepare_markup(
                _("Preserved libraries detected on the system.")),
            message_type=Gtk.MessageType.WARNING,
            context_id="PreservedLibsNotificationBox")

        self.add_button(_("_Update system now"), self._update)
        self.add_destroy_button(_("_Ignore"))

    def _update(self, button):
        """
        Update button callback from the updates notification box.
        """
        self.emit("upgrade-request")
