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
from gi.repository import Gtk, Pango, GObject, GLib

from rigo.utils import escape_markup
from rigo.ui.gtk3.widgets.notifications import NotificationBox

from entropy.i18n import _
from entropy.misc import ParallelTask
from entropy.services.client import WebService
from entropy.client.services.interfaces import Document, DocumentFactory

import entropy.tools

class CommentBox(Gtk.VBox):

    COMMENT_REMOVE_NOTIFICATION_CONTEXT = "CommentBoxRemoveContext"

    def __init__(self, nc, avc, webserv, comment, is_last=False):
        Gtk.VBox.__init__(self)
        self._nc = nc
        self._avc = avc
        self._webserv = webserv
        self._comment = comment
        self.set_name("comment-box")
        self.set_spacing(2)
        self._is_last = is_last
        self._header_label = Gtk.Label()

    def _on_activate_link(self, widget, uri):
        if uri == "remove":
            return self._on_remove_comment(widget)

    def _on_remove_comment(self, widget):
        """
        We are requested to remove this comment, spawn the request.
        """
        self.hide()
        task = ParallelTask(self._remove_comment)
        task.name = "RemoveComment{%s}" % (self._comment,)
        task.daemon = True
        task.start()
        return True

    def _remove_comment(self):
        """
        Remove comment routine.
        """
        try:
            self._webserv.remove_document(
                self._comment[Document.DOCUMENT_DOCUMENT_ID])
        except WebService.AuthenticationRequired as err:
            # ignore because we only show the remove link
            # when logged in.
            GLib.idle_add(self._show_removal_error, err)
            return
        except WebService.AuthenticationFailed as err:
            # ignore because we only show the remove link
            # when logged in.
            GLib.idle_add(self._show_removal_error, err)
            return
        except WebService.WebServiceException as err:
            GLib.idle_add(self._show_removal_error, err)
            return

        GLib.idle_add(self._show_removal_success)

    def _show_removal_error(self, err):
        """
        During Comment removal, the WebService raised an auth error
        """
        msg = "<b>%s</b>: %s" % (
            escape_markup(_("Cannot remove comment")),
            err)
        box = NotificationBox(
            msg,
            message_type=Gtk.MessageType.ERROR,
            context_id=self.COMMENT_REMOVE_NOTIFICATION_CONTEXT)

        box.add_destroy_button(_("_Ok, thanks"))
        self._nc.append(box)
        self.show()

    def _show_removal_success(self):
        """
        Comment has been removed successfully.
        """
        self.destroy()

    def _render_comment_header(self, *args):
        """
        Render the comment header label. This method can be
        called multiple times (to show/hide the remove link).
        """
        logged_username = None
        if self._webserv is not None:
            logged_username = self._webserv.get_credentials()

        ts_id = Document.DOCUMENT_TIMESTAMP_ID
        doc_username_id = DocumentFactory.DOCUMENT_USERNAME_ID
        doc_username = self._comment[doc_username_id]

        time_str = entropy.tools.convert_unix_time_to_human_time(
            self._comment[ts_id])
        time_str = escape_markup(time_str)

        remove_str = ""
        if logged_username == doc_username:
            remove_str = ", <b><a href=\"remove\">%s</a></b>" % (
                escape_markup(_("remove")),)

        self._header_label.set_markup(
            "<small><b>%s</b>" % (escape_markup(doc_username),) \
                + ", <i>" + time_str + "</i>" + remove_str \
                + "</small>")
        self._header_label.set_line_wrap(True)
        self._header_label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._header_label.set_alignment(0.0, 1.0)
        self._header_label.set_name("comment-box-author")

    def render(self):
        """
        Setup the CommentBox content. Shall be called once.
        """

        vbox = Gtk.VBox()

        self._render_comment_header()
        self._header_label.connect(
            "activate-link",
            self._on_activate_link)
        vbox.pack_start(self._header_label, False, False, 0)

        # title, keywords, ddata, document_id
        title = self._comment['title'].strip()

        if title:
            title_id = Document.DOCUMENT_TITLE_ID
            label = Gtk.Label()
            label_align = Gtk.Alignment()
            label_align.set_padding(0, 3, 0, 0)
            label_align.add(label)
            label.set_markup(
                "<b>" + escape_markup(self._comment[title_id]) + "</b>")
            label.set_name("comment-box-title")
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD)
            label.set_alignment(0.0, 0.0)
            label.set_selectable(True)
            vbox.pack_start(label_align, False, False, 0)

        data_id = Document.DOCUMENT_DATA_ID
        label = Gtk.Label()
        label_align = Gtk.Alignment()
        label_align.set_padding(0, 15, 0, 0)
        label_align.add(label)
        label.set_markup(
            "<small>"  + \
                escape_markup(self._comment[data_id]) + "</small>")
        label.set_name("comment-box-comment")
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_alignment(0.0, 0.0)
        label.set_selectable(True)
        vbox.pack_start(label_align, False, False, 0)

        self.pack_start(vbox, False, False, 0)

        self._avc.connect("logged-in", self._render_comment_header)
        self._avc.connect("logged-out", self._render_comment_header)

        vbox.show_all()
