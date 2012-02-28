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
from gi.repository import Gtk, Pango, GObject

from entropy.client.services.interfaces import Document, DocumentFactory

import entropy.tools

class CommentBox(Gtk.VBox):

    def __init__(self, comment, is_last=False):
        Gtk.VBox.__init__(self)
        self._comment = comment
        self.set_name("comment-box")
        self.set_spacing(2)
        self._is_last = is_last

    def render(self):

        vbox = Gtk.VBox()

        ts_id = Document.DOCUMENT_TIMESTAMP_ID
        user_id = DocumentFactory.DOCUMENT_USERNAME_ID
        label = Gtk.Label()
        time_str = entropy.tools.convert_unix_time_to_human_time(
            self._comment[ts_id])
        time_str = GObject.markup_escape_text(time_str)
        label.set_markup(
            "<small><b>%s</b>" % (self._comment[user_id],) \
                + ", <i>" + time_str + "</i>" \
                + "</small>")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.0, 1.0)
        label.set_selectable(True)
        label.set_name("comment-box-author")
        label.show()
        vbox.pack_start(label, False, False, 0)

        # title, keywords, ddata, document_id
        title = self._comment['title'].strip()

        if title:
            title_id = Document.DOCUMENT_TITLE_ID
            label = Gtk.Label()
            label.set_markup("<b>" + self._comment[title_id] + "</b>")
            label.set_name("comment-box-title")
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD)
            label.set_alignment(0.0, 0.0)
            label.set_selectable(True)
            label.show()
            vbox.pack_start(label, False, False, 0)

        data_id = Document.DOCUMENT_DATA_ID
        label = Gtk.Label()
        label.set_markup("<small>"  + self._comment[data_id] + "</small>")
        label.set_name("comment-box-comment")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.0, 0.0)
        label.set_selectable(True)
        label.show()
        vbox.pack_start(label, False, False, 0)

        if self._is_last:
            self.pack_start(vbox, False, False, 0)
        else:
            align = Gtk.Alignment()
            align.set_padding(0, 10, 0, 0)
            align.add(vbox)
            self.pack_start(align, False, False, 0)
            align.show_all()
