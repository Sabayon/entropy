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
import tempfile

from gi.repository import Gtk, GLib, GObject, Pango

from rigo.em import StockEms
from rigo.utils import build_register_url, open_url, escape_markup, \
    prepare_markup

from entropy.const import etpConst, const_convert_to_unicode, \
    const_debug_write
from entropy.i18n import _, ngettext
from entropy.services.client import WebService
from entropy.misc import ParallelTask

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
        button = Gtk.Button(text)
        button.set_use_underline(True)
        button.connect("clicked", clicked_callback)
        self._buttons.append(button)
        return button

    def add_widget(self, widget):
        """
        Add Gtk.Widget to the Buttons Area on the right.
        """
        self._widgets.append(widget)

    def add_destroy_button(self, text):
        """
        Add button that destroys the whole Notification object.
        """
        def _destroy(*args):
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

        NotificationBox.__init__(self, msg,
            tooltip=_("Updates available, how about installing them?"),
            message_type=Gtk.MessageType.WARNING,
            context_id="UpdatesNotificationBox")
        self.add_button(_("_Update System"), self._update)
        self.add_button(_("_Show"), self._show)
        self.add_destroy_button(_("_Ignore"))

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
            msg = _("The list of available Applications is old, <b>update now</b>?")
        else:
            msg = _("Repositories should be downloaded, <b>update now</b>?")

        NotificationBox.__init__(self, msg,
            tooltip=_("I dunno dude, I'd say Yes"),
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
            tooltip=_("You need to login to Entropy Web Services"),
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
                _("Login <b>error</b>!"))

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
            tooltip=_("Don't ask me..."),
            message_type=Gtk.MessageType.ERROR,
            context_id="ConnectivityNotificationBox")
        self.add_destroy_button(_("_Of course not"))


class PleaseWaitNotificationBox(NotificationBox):

    def __init__(self, message, context_id):

        NotificationBox.__init__(self, message,
            tooltip=_("A watched pot never boils"),
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
        else:
            msg = _("<b>%s</b> Application or one of its "
                    "dependencies is distributed with the following"
                    " licenses: %s")
            msg = msg % (self._app.name, ", ".join(lic_txts),)

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
            tooltip=_("Make sure to review all the licenses"),
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

            self._entropy.rwsem().reader_acquire()
            try:
                for repo_id in repos:
                    repo = self._entropy.open_repository(repo_id)
                    license_text = repo.retrieveLicenseText(uri)
                    if license_text is not None:
                        break
            finally:
                self._entropy.rwsem().reader_release()

            if license_text is not None:
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt")
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
                subprocess.call(["xdg-open", tmp_path])
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
