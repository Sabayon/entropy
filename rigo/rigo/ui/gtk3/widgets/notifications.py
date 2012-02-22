
from gi.repository import Gtk, GObject

from entropy.i18n import _


class NotificationBox(Gtk.HBox):

    """
    Generic notification widget to be used in the
    Rigo notification area.
    """

    def __init__(self, message, message_type=None, tooltip=None):
        Gtk.HBox.__init__(self)
        self._message = message
        self._buttons = []
        self._type = message_type
        if self._type is None:
            self._type = Gtk.MessageType.INFO
        self._tooltip = tooltip

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
        label = Gtk.Label()
        label.set_markup(self._message)
        # make it css-able
        label.set_name("notificationMessage")
        label.set_property("expand", True)
        label.set_alignment(0.02, 0.50)
        hbox.pack_start(label, True, True, 0)
        label.show()

        for button in self._buttons:
            hbox.pack_start(button, False, False, 3)
            button.show()

        content_area.set_property("expand", False)
        content_area.add(hbox)
        content_area.show()
        hbox.show()

        bar.show()
        bar.get_action_area().hide()
        self.pack_start(bar, True, True, 0)


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
            message_type=Gtk.MessageType.WARNING)
        self.add_button(_("_Update System"), self._update)
        self.add_button(_("_Show"), self._show)
        def _destroy(*args):
            self.destroy()
        self.add_button(_("_Ignore"), _destroy)

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
            message_type=Gtk.MessageType.ERROR)
        self.add_button(_("_Yes, why not?"), self._update)
        def _destroy(*args):
            self.destroy()
        self.add_button(_("_No, thanks"), _destroy)

    def _update(self, button):
        """
        Update button callback from the updates notification box.
        """
        self.emit("update-request")
