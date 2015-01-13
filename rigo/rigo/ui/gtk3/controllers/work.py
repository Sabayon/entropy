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

from gi.repository import GObject, GLib, Gtk, GdkPixbuf, Pango

from rigo.ui.gtk3.widgets.stars import Star
from rigo.ui.gtk3.widgets.terminal import TerminalWidget

from rigo.enums import Icons
from rigo.utils import escape_markup, prepare_markup
from RigoDaemon.enums import AppActions as DaemonAppActions

from entropy.i18n import _, ngettext

class WorkViewController(GObject.Object):

    APP_IMAGE_SIZE = 48

    def __init__(self, icons, rigo_service, work_box):
        self._icons = icons
        self._service = rigo_service
        self._box = work_box
        self._action_label = None
        self._appname_label = None
        self._app_image = None
        self._app_box = None
        self._progress_box = None
        self._stars = None
        self._terminal = None
        self._terminal_menu = None
        self._last_daemon_action = None
        self._autoscroll_mode = False

    def _setup_terminal_menu(self):
        """
        Setup TerminalWidget Right Click popup-menu.
        """
        self._terminal_menu = Gtk.Menu()

        sall_menu_item = Gtk.ImageMenuItem.new_from_stock(
            "gtk-select-all", None)
        sall_menu_item.connect("activate", self._on_terminal_select_all)
        self._terminal_menu.append(sall_menu_item)

        copy_menu_item = Gtk.ImageMenuItem.new_from_stock(
            "gtk-copy", None)
        copy_menu_item.connect("activate", self._on_terminal_copy)
        self._terminal_menu.append(copy_menu_item)

        reset_menu_item = Gtk.ImageMenuItem.new_from_stock(
            "gtk-clear", None)
        reset_menu_item.connect("activate", self._on_terminal_reset)
        self._terminal_menu.append(reset_menu_item)

        black_menu_item = Gtk.ImageMenuItem.new_with_label(
            escape_markup(_("Black on White")))
        black_menu_item.connect("activate", self._on_terminal_color, True)
        self._terminal_menu.append(black_menu_item)

        white_menu_item = Gtk.ImageMenuItem.new_with_label(
            escape_markup(_("White on Black")))
        white_menu_item.connect("activate", self._on_terminal_color, False)
        self._terminal_menu.append(white_menu_item)

        self._autoscroll_enable_text = escape_markup(
            _("Enable automatic scrolling"))
        self._autoscroll_disable_text = escape_markup(
            _("Disable automatic scrolling"))
        self._autoscroll_menu_item = Gtk.ImageMenuItem.new_with_label(
            self._autoscroll_enable_text)
        self._autoscroll_menu_item.connect(
            "activate", self._on_terminal_autoscroll)
        self._terminal_menu.append(self._autoscroll_menu_item)

        self._terminal_menu.show_all()

    def _setup_terminal_area(self):
        """
        Setup TerminalWidget area (including ScrollBar).
        """
        terminal_align = Gtk.Alignment()
        terminal_align.set_padding(10, 0, 0, 0)
        self._terminal_expander = Gtk.Expander.new(
            prepare_markup(
                _("<i>Show <b>Application Management</b> Progress</i>")))
        self._terminal_expander.set_use_markup(True)
        hbox = Gtk.HBox()

        self._terminal = TerminalWidget()
        self._terminal.connect(
            "button-press-event",
            self._on_terminal_click)
        self._terminal.reset()
        self._terminal.autoscroll(self._autoscroll_mode)

        hbox.pack_start(self._terminal, True, True, 0)

        scrollbar = Gtk.VScrollbar.new(self._terminal.get_property("vadjustment"))
        hbox.pack_start(scrollbar, False, False, 0)
        self._terminal_expander.add(hbox)
        terminal_align.add(self._terminal_expander)
        terminal_align.show_all()

        return terminal_align

    def _setup_progress_area(self):
        """
        Setup Progress Bar area.
        """
        self._progress_box = Gtk.VBox()

        progress_align = Gtk.Alignment()
        progress_align.set_padding(10, 0, 0, 0)
        self._progress_bar_shown = True
        self._progress_bar = Gtk.ProgressBar()
        progress_align.add(self._progress_bar)
        self._progress_box.pack_start(progress_align, False, False, 0)
        self._progress_box.show_all()
        self.reset_progress() # hide progress bar

        return self._progress_box

    def _setup_app_area(self):
        """
        Setup Application Information Area.
        """
        self._app_box = Gtk.VBox()

        hbox = Gtk.HBox()

        self._missing_icon = self._icons.load_icon(
            Icons.MISSING_APP,
            self.APP_IMAGE_SIZE, 0)

        # Image
        image_box = Gtk.VBox()
        self._app_image = Gtk.Image.new_from_pixbuf(
            self._missing_icon)

        stars_align = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        stars_align.set_padding(5, 0, 0, 0)
        self._stars = Star()
        stars_align.add(self._stars)
        self._stars.set_size_as_pixel_value(16)

        image_box.pack_start(self._app_image, False, False, 0)
        image_box.pack_start(stars_align, False, False, 0)

        hbox.pack_start(image_box, False, False, 0)

        # Action, App Name & Description
        name_align = Gtk.Alignment()
        name_align.set_padding(0, 0, 5, 0)
        name_box = Gtk.VBox()

        action_align = Gtk.Alignment()
        self._action_label = Gtk.Label(label="Action")
        self._action_label.set_alignment(0.0, 0.0)
        action_align.add(self._action_label)
        action_align.set_padding(0, 4, 0, 0)

        self._appname_label = Gtk.Label(label="App Name")
        self._appname_label.set_line_wrap(True)
        self._appname_label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._appname_label.set_alignment(0.0, 1.0)

        name_box.pack_start(action_align, False, False, 0)
        name_box.pack_start(self._appname_label, True, True, 0)
        name_align.add(name_box)

        hbox.pack_start(name_align, True, True, 5)

        self._app_box.pack_start(hbox, False, False, 5)

        return self._app_box

    def setup(self):
        """
        Initialize WorkViewController controlled resources.
        """
        self._setup_terminal_menu()

        box = self._setup_app_area()
        self._box.pack_start(box, False, False, 0)

        box = self._setup_progress_area()
        self._box.pack_start(box, False, False, 0)

        box = self._setup_terminal_area()
        self._box.pack_start(box, True, True, 0)

        self._service.set_terminal(self._terminal)

        self.deactivate_progress_bar()
        self.deactivate_app_box()

    def activate_app_box(self):
        """
        Activate the Application Box showing information
        about the Application being currently handled.
        """
        self._app_box.show_all()

    def deactivate_app_box(self):
        """
        Deactivate the Application Box showing information
        about the Application being currently handled.
        """
        self._app_box.hide()

    def activate_progress_bar(self):
        """
        Activate the Progress Bar showing progress information.
        """
        self._progress_box.show_all()

    def deactivate_progress_bar(self):
        """
        Deactivate the Progress Bar showing progress information.
        """
        self._progress_box.hide()

    def _set_application_icon(self, app):
        """
        Set Application Icon image.
        """
        icon, cache_hit = app.get_icon()
        if icon is None:
            self._app_image.set_from_pixbuf(
                self._missing_icon)
            return

        icon_path = icon.local_document()
        if not os.path.isfile(icon_path):
            self._app_image.set_from_pixbuf(
                self._missing_icon)
            return

        try:
            img = Gtk.Image.new_from_file(icon_path)
        except GObject.GError:
            img = None

        width = self.APP_IMAGE_SIZE
        height = self.APP_IMAGE_SIZE
        img_buf = None
        if img is not None:
            img_buf = img.get_pixbuf()
        if img_buf is not None:
            w, h = img_buf.get_width(), \
                img_buf.get_height()
            if w >= 1:
                height = width * h / w

        del img_buf
        del img

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                icon_path, width, height)
            if pixbuf is not None:
                self._app_image.set_from_pixbuf(pixbuf)
            else:
                self._app_image.set_from_pixbuf(
                    self._missing_icon)
        except GObject.GError:
            self._app_image.set_from_pixbuf(
                self._missing_icon)

    def update_queue_information(self, queue_len):
        """
        Update Action Queue related info.
        """
        daemon_action = self._last_daemon_action
        msg = None
        if daemon_action == DaemonAppActions.INSTALL:
            msg = _("Installing")
        elif daemon_action == DaemonAppActions.REMOVE:
            msg = _("Removing")

        if msg is not None:
            more_msg = ""
            queue_len -= 1
            queue_len = max(0, queue_len)
            if queue_len:
                more_msg = ngettext(
                    ", and <b>%d</b> <i>more in queue</i>",
                    ", and <b>%d</b> <i>more in queue</i>",
                    queue_len)
                more_msg = prepare_markup(more_msg % (queue_len,))

            self._action_label.set_markup(
                "<big><b>%s</b>%s</big>" % (
                    escape_markup(msg),
                    more_msg,))

    def expand_terminal(self):
        """
        Expand Terminal widget.
        """
        self._terminal_expander.set_expanded(True)

    def set_application(self, app, daemon_action):
        """
        Set Application information by providing its Application
        object.
        """
        # this is used to update action_label
        self._last_daemon_action = daemon_action
        queue_len = self._service.action_queue_length()
        self.update_queue_information(queue_len)

        extended_markup = app.get_extended_markup()

        self._appname_label.set_markup(extended_markup)

        self._set_application_icon(app)

        # rating
        stats = app.get_review_stats()
        self._stars.set_rating(stats.ratings_average)

        self.activate_app_box()
        self._app_box.queue_draw()

    def reset_progress(self):
        """
        Reset Progress Bar to intial state.
        """
        self._progress_bar.set_show_text(False)
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.hide()
        self._progress_bar_shown = False

    def set_progress(self, fraction, text=None):
        """
        Set Progress Bar progress, progress must be a value between
        0.0 and 1.0. You can also provide a new text for progress at
        the same time, the same will be escaped and cleaned out
        by the callee.
        """
        if not self._progress_bar_shown:
            self._progress_bar.show()
            self._progress_bar_shown = True
        self._progress_bar.set_fraction(fraction)
        if text is not None:
            self._progress_bar.set_text(escape_markup(text))
        self._progress_bar.set_show_text(text is not None)

    def set_progress_text(self, text):
        """
        Set Progress Bar text. The same will be escaped and cleaned out by
        the callee.
        """
        if not self._progress_bar_shown:
            self._progress_bar.show()
            self._progress_bar_shown = True
        self._progress_bar.set_text(escape_markup(text))

    def _on_terminal_click(self, widget, event):
        """
        Right Click on the TerminalWidget area.
        """
        if event.button == 3:
            self._terminal_menu.popup(
                None, None, None, None, event.button, event.time)

    def _on_terminal_copy(self, widget):
        """
        Copy to clipboard Terminal GtkMenuItem clicked.
        """
        self._terminal.copy_clipboard()

    def _on_terminal_reset(self, widget):
        """
        Reset Terminal GtkMenuItem clicked.
        """
        self._terminal.reset()

    def _on_terminal_select_all(self, widget):
        """
        Select All Terminal GtkMenuItem clicked.
        """
        self._terminal.select_all()

    def _on_terminal_color(self, widget, white):
        """
        Set the Terminal colors.
        """
        if white:
            self._terminal.white()
        else:
            self._terminal.black()

    def _on_terminal_autoscroll(self, widget):
        """
        Toggle the terminal autoscroll mode.
        """
        mode = not self._autoscroll_mode
        self._autoscroll_mode = mode
        if mode:
            text = self._autoscroll_disable_text
        else:
            text = self._autoscroll_enable_text

        self._autoscroll_menu_item.set_label(text)
        self._terminal.autoscroll(mode)
