# Copyright (C) 2012 Fabio Erculiani
#
# Authors:
#  Fabio Erculiani
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

from gi.repository import Gtk, Pango, GObject

from entropy.client.services.interfaces import Document, DocumentFactory

import entropy.tools

class CommentBox(Gtk.VBox):

    def __init__(self, comment, is_last=False):
        Gtk.VBox.__init__(self)
        self._comment = comment
        self.set_name("commentBox")
        self.set_spacing(2)
        self._is_last = is_last

    def render(self):
        # title, keywords, ddata, document_id
        title = self._comment['title'].strip()

        if title:
            title_id = Document.DOCUMENT_TITLE_ID
            label = Gtk.Label()
            label.set_markup("<b>" + self._comment[title_id] + "</b>")
            label.set_name("commentBoxTitle")
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD)
            label.set_alignment(0.0, 0.0)
            label.set_selectable(True)
            label.show()
            self.pack_start(label, False, False, 0)

        data_id = Document.DOCUMENT_DATA_ID
        label = Gtk.Label()
        label.set_markup("<small>"  + self._comment[data_id] + "</small>")
        label.set_name("commentBoxComment")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.0, 0.0)
        label.set_selectable(True)
        label.show()
        self.pack_start(label, False, False, 0)

        ts_id = Document.DOCUMENT_TIMESTAMP_ID
        user_id = DocumentFactory.DOCUMENT_USERNAME_ID
        label = Gtk.Label()
        time_str = entropy.tools.convert_unix_time_to_human_time(
            self._comment[ts_id])
        time_str = GObject.markup_escape_text(time_str)
        label.set_markup(
            "<small><i>"  + time_str \
                + "</i>, <b>%s</b>" % (self._comment[user_id],) \
                + "</small>")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.98, 0.0)
        label.set_selectable(True)
        label.set_name("commentBoxAuthor")
        label.show()
        self.pack_start(label, False, False, 0)

        if not self._is_last:
            image = Gtk.Image.new_from_icon_name("comment-separator",
                                                 Gtk.IconSize.BUTTON)
            image.set_pixel_size(50)
            self.pack_start(image, False, False, 0)
            image.show()
