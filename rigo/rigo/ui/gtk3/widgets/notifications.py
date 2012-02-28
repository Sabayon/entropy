
import subprocess

from gi.repository import Gtk, GLib, GObject

from rigo.utils import build_register_url, open_url

from entropy.i18n import _
from entropy.services.client import WebService
from entropy.misc import ParallelTask



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
            # make it css-able
            label.set_property("expand", True)
            label.set_alignment(0.02, 0.50)
            message_hbox.pack_start(label, True, True, 0)
        else:
            message_hbox.pack_start(self._message_widget, True, True, 0)
        hbox.pack_start(message_hbox, True, True, 0)

        button_hbox = Gtk.HBox()
        button_hbox.set_name("button-area")
        for button in self._buttons:
            button_hbox.pack_start(button, False, False, 3)
        hbox.pack_start(button_hbox, False, False, 2)

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

    def __init__(self, entropy_client, avc):
        self._entropy = entropy_client
        self._avc = avc

        msg = _("The list of available applications is old, <b>update now</b>?")

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

    def __init__(self, entropy_ws, app, context_id=None):
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
        username_label = Gtk.Label()
        username_label.set_markup(_("Username:"))
        hbox.pack_start(username_label, False, False, 2)

        self._username_entry = Gtk.Entry()
        hbox.pack_start(self._username_entry, False, False, 0)

        password_label = Gtk.Label()
        password_label.set_markup(_(", password:"))
        hbox.pack_start(password_label, False, False, 2)

        self._password_entry = Gtk.Entry()
        self._password_entry.set_visibility(False)
        hbox.pack_start(self._password_entry, False, False, 0)

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
            GLib.idle_add(self.destroy)
        GLib.idle_add(_emit_success)

    def _login(self, button):
        """
        Try to login to Entropy Web Services.
        """
        username = self._username_entry.get_text()
        password = self._password_entry.get_text()

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
