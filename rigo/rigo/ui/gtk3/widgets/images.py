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
from threading import Lock

from gi.repository import Gtk, Gdk, Pango, GObject, GdkPixbuf

from rigo.utils import escape_markup
from rigo.ui.gtk3.utils import get_sc_icon_theme
from rigo.paths import DATA_DIR
from rigo.enums import Icons
from rigo.utils import open_url
from rigo.ui.gtk3.models.appliststore import AppListStore

from entropy.client.services.interfaces import Document, DocumentFactory
from entropy.i18n import _

import entropy.tools


class ImageBox(Gtk.VBox):

    IMAGE_SIZE = 160
    _MISSING_ICON = None
    _MISSING_ICON_MUTEX = Lock()
    _ICONS = None
    _ICONS_MUTEX = Lock()
    _hand = Gdk.Cursor.new(Gdk.CursorType.HAND2)

    def __init__(self, image, is_last=False):
        Gtk.VBox.__init__(self)
        self._image = image
        self.set_name("image-box")
        self.set_spacing(2)
        self._is_last = is_last

    @property
    def _icons(self):
        """
        Get Icons Theme Object.
        """
        if ImageBox._ICONS is not None:
            return ImageBox._ICONS
        with ImageBox._ICONS_MUTEX:
            if ImageBox._ICONS is not None:
                return ImageBox._ICONS
            _icons = get_sc_icon_theme(DATA_DIR)
            AppListStore._ICONS = _icons
            return _icons

    @property
    def _missing_icon(self):
        """
        Return the missing icon Gtk.Image() if needed.
        """
        if ImageBox._MISSING_ICON is not None:
            return ImageBox._MISSING_ICON
        with ImageBox._MISSING_ICON_MUTEX:
            if ImageBox._MISSING_ICON is not None:
                return ImageBox._MISSING_ICON
            _missing_icon = self._icons.load_icon(
            Icons.MISSING_APP, ImageBox.IMAGE_SIZE, 0)
            ImageBox._MISSING_ICON = _missing_icon
            return _missing_icon

    def _on_image_clicked(self, widget, event):
        """
        Image clicked event, load image in browser.
        """
        url = self._image.document_url()
        if url is not None:
            open_url(url)

    def _on_image_enter(self, widget, event):
        """
        Cursor over image, switch cursor.
        """
        widget.get_window().set_cursor(ImageBox._hand)

    def _on_image_leave(self, widget, event):
        """
        Cursor leaving image, switch cursor.
        """
        widget.get_window().set_cursor(None)

    def render(self):

        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        vbox.pack_start(hbox, False, False, 0)

        use_missing = False
        image_path = self._image.local_document()
        if not os.path.isfile(image_path):
            img_buf = self._missing_icon
            use_missing = True
        else:
            img = Gtk.Image.new_from_file(image_path)
            img_buf = img.get_pixbuf()
            if img_buf is None:
                use_missing = True
                img_buf = self._missing_icon
            del img

        w, h = img_buf.get_width(), img_buf.get_height()
        del img_buf
        if w < 1:
            # not legit
            use_missing = True
            img_buf = self._missing_icon

        width = ImageBox.IMAGE_SIZE
        height = width * h / w

        if not use_missing:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    image_path, width, height)
            except GObject.GError:
                try:
                    os.remove(image_path)
                except OSError:
                    pass
                pixbuf = self._missing_icon
                use_missing = True
        else:
            pixbuf = self._missing_icon

        event_image = Gtk.EventBox()
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        event_image.add(image)
        event_image.connect("button-press-event", self._on_image_clicked)
        event_image.connect("leave-notify-event", self._on_image_leave)
        event_image.connect("enter-notify-event", self._on_image_enter)
        hbox.pack_start(event_image, False, False, 2)

        right_vbox = Gtk.VBox()
        right_align = Gtk.Alignment()
        right_align.set_padding(0, 0, 8, 0)
        right_align.add(right_vbox)

        ts_id = Document.DOCUMENT_TIMESTAMP_ID
        user_id = DocumentFactory.DOCUMENT_USERNAME_ID
        label = Gtk.Label()
        time_str = entropy.tools.convert_unix_time_to_human_time(
            self._image[ts_id])
        time_str = escape_markup(time_str)
        label.set_markup(
            "<small><b>%s</b>" % (escape_markup(self._image[user_id]),) \
                + ", <i>" + time_str + "</i>" \
                + "</small>")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.0, 1.0)
        label.set_selectable(True)
        label.set_name("image-box-author")
        right_vbox.pack_start(label, False, False, 0)

        # title, keywords, ddata, document_id
        title = self._image['title'].strip()

        if title:
            title_id = Document.DOCUMENT_TITLE_ID
            label = Gtk.Label()
            label.set_markup(
                "<b>" + escape_markup(self._image[title_id]) + "</b>")
            label.set_name("image-box-title")
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD)
            label.set_alignment(0.0, 0.0)
            label.set_selectable(True)
            right_vbox.pack_start(label, False, False, 0)

        desc_id = Document.DOCUMENT_DESCRIPTION_ID
        label = Gtk.Label()
        label_align = Gtk.Alignment()
        label_align.set_padding(0, 5, 0, 0)
        label_align.add(label)
        label.set_markup(
            "<small>"  + escape_markup(self._image[desc_id]) + "</small>")
        label.set_name("image-box-description")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.0, 0.0)
        label.set_selectable(True)
        right_vbox.pack_start(label_align, False, False, 0)

        keywords_id = Document.DOCUMENT_KEYWORDS_ID
        label = Gtk.Label()
        keywords_txt = "<b>%s:</b> " % (escape_markup(_("Keywords")),)
        label.set_markup(
            "<small>" + keywords_txt + \
                escape_markup(self._image[keywords_id]) + "</small>")
        label.set_name("image-box-keywords")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.0, 0.0)
        label.set_selectable(True)
        right_vbox.pack_start(label, False, False, 0)

        hbox.pack_start(right_align, True, True, 0)

        self.pack_start(vbox, False, False, 0)
        vbox.show_all()
