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
import sys
import copy
import tempfile
import time
from threading import Lock

sys.path.insert(0, "../lib")
sys.path.insert(1, "../client")
sys.path.insert(2, "./")
sys.path.insert(3, "/usr/lib/entropy/lib")
sys.path.insert(4, "/usr/lib/entropy/client")
sys.path.insert(5, "/usr/lib/entropy/rigo")


from gi.repository import Gtk, Gdk, Gio, GLib, GObject

from rigo.paths import DATA_DIR
from rigo.enums import Icons
from rigo.entropyapi import EntropyWebService
from rigo.models.application import Application, ApplicationMetadata
from rigo.ui.gtk3.widgets.apptreeview import AppTreeView
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    RepositoriesUpdateNotificationBox, UpdatesNotificationBox, \
    LoginNotificationBox, ConnectivityNotificationBox
from rigo.ui.gtk3.widgets.welcome import WelcomeBox
from rigo.ui.gtk3.widgets.stars import ReactiveStar
from rigo.ui.gtk3.widgets.comments import CommentBox
from rigo.ui.gtk3.widgets.images import ImageBox
from rigo.ui.gtk3.models.appliststore import AppListStore
from rigo.ui.gtk3.utils import init_sc_css_provider, get_sc_icon_theme
from rigo.utils import build_application_store_url, build_register_url, \
    escape_markup

from entropy.const import etpUi, const_debug_write, const_debug_enabled, \
    const_convert_to_unicode
from entropy.client.interfaces import Client
from entropy.client.interfaces.repository import Repository
from entropy.services.client import WebService
from entropy.misc import TimeScheduled, ParallelTask
from entropy.i18n import _, ngettext

import entropy.tools


class ApplicationsViewController(GObject.Object):

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
                 search_entry, store, view):
        GObject.Object.__init__(self)
        self._entropy = entropy_client
        self._icons = icons
        self._entropy_ws = entropy_ws
        self._search_entry = search_entry
        self._store = store
        self._view = view

    def _search_icon_release(self, search_entry, icon_pos, _other):
        """
        Event associated to the Search bar icon click.
        Here we catch secondary icon click to reset the search entry text.
        """
        if search_entry is not self._search_entry:
            return
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            search_entry.set_text("")
            self.clear()
            search_entry.emit("changed")
        elif self._store.get_iter_first():
            # primary icon click will force UI to switch to Browser mode
            self.emit("view-filled")

    def _search_changed(self, search_entry):
        GLib.timeout_add(700, self._search, search_entry.get_text())

    def _search(self, old_text):
        cur_text = self._search_entry.get_text()
        if cur_text == old_text and cur_text:
            th = ParallelTask(self.__search_thread, copy.copy(old_text))
            th.name = "SearchThread"
            th.start()

    def __search_thread(self, text):
        def _prepare_for_search(txt):
            return txt.replace(" ", "-").lower()

        matches = []
        pkg_matches, rc = self._entropy.atom_match(
            text, multi_match = True,
            multi_repo = True, mask_filter = False)
        matches.extend(pkg_matches)
        search_matches = self._entropy.atom_search(
            _prepare_for_search(text),
            repositories = self._entropy.repositories())
        matches.extend([x for x in search_matches if x not in matches])
        self.set_many_safe(matches)

    def setup(self):
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


class NotificationViewController(GObject.Object):

    """
    Notification area widget controller.
    This class features the handling of some built-in
    Notification objects (like updates and outdated repositories)
    but also accepts external NotificationBox instances as well.
    """

    def __init__(self, entropy_client, entropy_ws, avc, notification_box):
        GObject.Object.__init__(self)
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._avc = avc
        self._box = notification_box
        self._updates = None
        self._security_updates = None
        self._context_id_map = {}

    def setup(self):
        GLib.timeout_add(3000, self._calculate_updates)
        GLib.idle_add(self._check_connectivity)

    def _check_connectivity(self):
        th = ParallelTask(self.__check_connectivity)
        th.daemon = True
        th.name = "CheckConnectivity"
        th.start()

    def _calculate_updates(self):
        th = ParallelTask(self.__calculate_updates)
        th.daemon = True
        th.name = "CalculateUpdates"
        th.start()

    def __check_connectivity(self):
        """
        Execute connectivity check basing on Entropy
        Web Services availability.
        """
        repositories = self._entropy.repositories()
        available = False
        for repository_id in repositories:
            if self._entropy_ws.get(repository_id) is not None:
                available = True
                break

        if not available:
            GLib.idle_add(self._notify_connectivity_issues)

    def __order_updates(self, updates):
        """
        Order updates using PN.
        """
        def _key_func(x):
            return self._entropy.open_repository(
                x[1]).retrieveName(x[0])
        return sorted(updates, key=_key_func)

    def __calculate_updates(self):
        if Repository.are_repositories_old():
            GLib.idle_add(self._notify_old_repositories_safe)
            return

        updates, removal, fine, spm_fine = \
            self._entropy.calculate_updates()
        self._updates = self.__order_updates(updates)
        self._security_updates = self._entropy.calculate_security_updates()
        GLib.idle_add(self._notify_updates_safe)

    def _notify_connectivity_issues(self):
        """
        Cannot connect to Entropy Web Services.
        """
        box = ConnectivityNotificationBox()
        self.append(box)

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
        """
        Callback requesting Packages Update.
        """
        # FIXME, lxnay complete
        print("On Upgrade Request Received", args)

    def _on_update(self, *args):
        """
        Callback requesting Repositories Update.
        """
        # FIXME, lxnay complete
        print("On Update Request Received", args)

    def _on_update_show(self, *args):
        """
        Callback from UpdatesNotification "Show" button.
        Showing updates.
        """
        self._avc.set_many_safe(self._updates)

    def append(self, box, timeout=None, context_id=None):
        """
        Append a notification to the Notification area.
        context_id is used to automatically drop any other
        notification exposing the same context identifier.
        """
        context_id = box.get_context_id()
        if context_id is not None:
            old_box = self._context_id_map.get(context_id)
            if old_box is not None:
                old_box.destroy()
            self._context_id_map[context_id] = box
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
            self._context_id_map.pop(box.get_context_id(), None)
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
            child.destroy()
        self._context_id_map.clear()

    def clear_safe(self):
        """
        Thread-safe version of clear().
        """
        GLib.idle_add(self.clear)


class ApplicationViewController(GObject.Object):
    """
    Applications View Container, exposing all the events
    that can happen to Applications listed in the contained
    TreeView.
    """

    class WindowedReactiveStar(ReactiveStar):

        def __init__(self, window):
            self._window = window
            self._hand = Gdk.Cursor.new(Gdk.CursorType.HAND2)
            ReactiveStar.__init__(self)

        def on_enter_notify(self, widget, event):
            self._window.get_window().set_cursor(self._hand)

        def on_leave_notify(self, widget, event):
            self._window.get_window().set_cursor(None)

    __gsignals__ = {
        # Double click on application widget
        "application-activated"  : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        # Show Application in the Rigo UI
        "application-show"  : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        # Hide Application in the Rigo UI
        "application-hide"  : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        # Single click on application widget
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT,),
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

    VOTE_NOTIFICATION_CONTEXT_ID = "VoteNotificationContext"
    COMMENT_NOTIFICATION_CONTEXT_ID = "CommentNotificationContext"

    def __init__(self, entropy_client, entropy_ws, builder):
        GObject.Object.__init__(self)
        self._builder = builder
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._app_store = None
        self._last_app = None
        self._nc = None

        self._window = self._builder.get_object("rigoWindow")
        self._image = self._builder.get_object("appViewImage")
        self._app_name_lbl = self._builder.get_object("appViewNameLabel")
        self._app_info_lbl = self._builder.get_object("appViewInfoLabel")
        self._app_downloaded_lbl = self._builder.get_object(
            "appViewDownloadedLabel")
        self._app_comments_box = self._builder.get_object("appViewCommentsVbox")
        self._app_comments_box.set_name("comments-box")
        self._app_comments_align = self._builder.get_object(
            "appViewCommentsAlign")
        self._app_my_comments_box = self._builder.get_object(
            "appViewMyCommentsVbox")
        self._app_my_comments_align = self._builder.get_object(
            "appViewMyCommentsAlign")
        self._app_my_comments_box.set_name("comments-box")
        self._app_comment_send_button = self._builder.get_object(
            "appViewCommentSendButton")
        self._app_comment_text_view = self._builder.get_object(
            "appViewCommentText")
        self._app_comment_text_view.set_name("rigo-text-view")
        self._app_comment_text_buffer = self._builder.get_object(
            "appViewCommentTextBuffer")
        self._app_comment_more_label = self._builder.get_object(
            "appViewCommentMoreLabel")
        self._stars_container = self._builder.get_object("appViewStarsSelVbox")

        self._stars = ApplicationViewController.WindowedReactiveStar(
            self._window)
        self._stars_alignment = Gtk.Alignment.new(0.0, 0.5, 1.0, 1.0)
        self._stars_alignment.set_padding(0, 5, 0, 0)
        self._stars_alignment.add(self._stars)
        self._stars.set_size_as_pixel_value(24)

        self._stars_container.pack_start(self._stars_alignment, False, False, 0)

        self._app_images_box = self._builder.get_object(
            "appViewImagesVbox")

    def set_notification_controller(self, nc):
        """
        Bind NotificationController object to this class.
        """
        self._nc = nc

    def set_store(self, store):
        """
        Bind AppListStore object to this class.
        """
        self._app_store = store

    def setup(self):
        self.connect("application-activated", self._on_application_activated)
        self._app_store.connect("redraw-request", self._on_redraw_request)
        self._app_comment_send_button.connect("clicked", self._on_send_comment)
        self._app_comment_send_button.set_sensitive(False)
        self._app_comment_text_buffer.connect(
            "changed", self._on_comment_buffer_changed)
        self._stars.connect("changed", self._on_stars_clicked)

    def _on_comment_buffer_changed(self, widget):
        """
        Our comment text is changed, decide if to activate the Send button.
        """
        count = self._app_comment_text_buffer.get_char_count()
        found = count != 0
        self._app_comment_send_button.set_sensitive(found)

    def _on_application_activated(self, avc, app):
        """
        Event received from Gtk widgets requesting us to load package
        information. Once we're done loading the shit, we just emit
        'application-show' and let others do the UI switch.
        """
        self._last_app = app
        task = ParallelTask(self.__application_activate, app)
        task.name = "ApplicationActivate"
        task.daemon = True
        task.start()

    def _on_redraw_request(self, widget, pkg_match):
        """
        Redraw request received from AppListStore for given package match.
        We are required to update rating, number of downloads, icon.
        """
        if self._last_app is None:
            return
        if pkg_match == self._last_app.get_details().pkg:
            stats = self._app_store.get_review_stats(pkg_match)
            icon = self._app_store.get_icon(pkg_match)
            self._setup_application_stats(stats, icon)

    def _on_stars_clicked(self, widget, app=None):
        """
        Stars clicked, user wants to vote.
        """
        if app is None:
            app = self._last_app
            if app is None:
                # wtf
                return

        def _sender(app, vote):
            if not app.is_webservice_available():
                GLib.idle_add(self._notify_webservice_na, app,
                              self.VOTE_NOTIFICATION_CONTEXT_ID)
                return
            ws_user = app.get_webservice_username()
            if ws_user is not None:
                GLib.idle_add(self._notify_vote_submit, app, ws_user, vote)
            else:
                GLib.idle_add(self._notify_login_request, app, vote,
                              self._on_stars_login_success,
                              self._on_stars_login_failed,
                              self.VOTE_NOTIFICATION_CONTEXT_ID)

        vote = int(self._stars.get_rating()) # is float
        task = ParallelTask(_sender, app, vote)
        task.name = "AppViewSendVote"
        task.start()

    def _on_stars_login_success(self, widget, username, app):
        """
        Notify user that we successfully logged in!
        """
        box = NotificationBox(
            _("Logged in as <b>%s</b>! How about your <b>vote</b>?") \
                % (escape_markup(username),),
            message_type=Gtk.MessageType.INFO,
            context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)

        def _send_vote(widget):
            self._on_stars_clicked(self._stars, app=app)
        box.add_button(_("_Vote now"), _send_vote)

        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _on_stars_login_failed(self, widget, app):
        """
        Entropy Web Services Login failed message.
        """
        box = NotificationBox(
            _("Login failed. Your <b>vote</b> hasn't been added"),
            message_type=Gtk.MessageType.ERROR,
            context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
        box.add_destroy_button(_("_Ok, thanks"))
        self._nc.append(box)

    def _notify_vote_submit(self, app, username, vote):
        """
        Notify User about Comment submission with current credentials.
        """
        box = NotificationBox(
            _("Rate <b>%s</b> as <b>%s</b>, with <b>%d</b> stars?") \
                % (app.name, escape_markup(username),
                   vote,),
            message_type=Gtk.MessageType.INFO,
            context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)

        def _vote_submit(widget):
            self._vote_submit(app, username, vote)
        box.add_button(_("_Ok, cool!"), _vote_submit)

        def _send_vote():
            self._on_stars_clicked(self._stars, app=app)
        def _logout_webservice(widget):
            self._logout_webservice(app, _send_vote)
        box.add_button(_("_No, logout!"), _logout_webservice)

        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _vote_submit(self, app, username, vote):
        """
        Do the actual vote submit.
        """
        task = ParallelTask(
            self._vote_submit_thread_body,
            app, username, vote)
        task.name = "VoteSubmitThreadBody"
        task.daemon = True
        task.start()

    def _vote_submit_thread_body(self, app, username, vote):
        """
        Called by _vote_submit(), does the actualy submit.
        """
        repository_id = app.get_details().channelname
        webserv = self._entropy_ws.get(repository_id)
        if webserv is None:
            # impossible!
            return

        key = app.get_details().pkgkey

        err_msg = None
        try:
            voted = webserv.add_vote(
                key, vote)
        except WebService.WebServiceException as err:
            voted = False
            err_msg = str(err)

        def _submit_success():
            nbox = NotificationBox(
                _("Your vote has been added!"),
                message_type=Gtk.MessageType.INFO,
                context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
            nbox.add_destroy_button(_("Ok, great!"))
            self._nc.append(nbox, timeout=10)
            self._on_redraw_request(None, app.get_details().pkg)

        def _submit_fail(err_msg):
            if err_msg is None:
                box = NotificationBox(
                    _("You already voted this <b>Application</b>"),
                    message_type=Gtk.MessageType.ERROR,
                    context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
            else:
                box = NotificationBox(
                    _("Vote error: <i>%s</i>") % (err_msg,),
                    message_type=Gtk.MessageType.ERROR,
                    context_id=self.VOTE_NOTIFICATION_CONTEXT_ID)
            box.add_destroy_button(_("Ok, thanks"))
            self._nc.append(box)

        if voted:
            GLib.idle_add(_submit_success)
        else:
            GLib.idle_add(_submit_fail, err_msg)

    def __application_activate(self, app):
        """
        Collect data from app, then call the UI setup in the main loop.
        """
        details = app.get_details()
        metadata = {}
        metadata['markup'] = app.get_extended_markup()
        metadata['info'] = app.get_info_markup()
        metadata['download_size'] = details.downsize
        metadata['stats'] = app.get_review_stats()
        metadata['homepage'] = details.website
        metadata['date'] = details.date
        # using app store here because we cache the icon pixbuf
        metadata['icon'] = self._app_store.get_icon(details.pkg)
        GLib.idle_add(self._setup_application_info, app, metadata)

    def hide(self):
        """
        This method shall be called when the Controller widgets are
        going to hide.
        """
        self._last_app = None
        for child in self._app_my_comments_box.get_children():
            child.destroy()
        self.emit("application-hide", self)

    def _on_send_comment(self, widget, app=None):
        """
        Send comment to Web Service.
        """
        if app is None:
            app = self._last_app
            if app is None:
                # we're hiding
                return

        text = self._app_comment_text_buffer.get_text(
            self._app_comment_text_buffer.get_start_iter(),
            self._app_comment_text_buffer.get_end_iter(),
            False)
        if not text.strip():
            return
        # make it utf-8
        text = const_convert_to_unicode(text, enctype="utf-8")

        def _sender(app, text):
            if not app.is_webservice_available():
                GLib.idle_add(self._notify_webservice_na, app,
                              self.COMMENT_NOTIFICATION_CONTEXT_ID)
                return
            ws_user = app.get_webservice_username()
            if ws_user is not None:
                GLib.idle_add(self._notify_comment_submit, app, ws_user, text)
            else:
                GLib.idle_add(self._notify_login_request, app, text,
                              self._on_comment_login_success,
                              self._on_comment_login_failed,
                              self.COMMENT_NOTIFICATION_CONTEXT_ID)

        task = ParallelTask(_sender, app, text)
        task.name = "AppViewSendComment"
        task.start()

    def _notify_webservice_na(self, app, context_id):
        """
        Notify Web Service unavailability for given Application object.
        """
        box = NotificationBox(
            "%s: <b>%s</b>" % (
                _("Entropy Web Services not available for repository"),
                app.get_details().channelname),
            message_type=Gtk.MessageType.ERROR,
            context_id=context_id)
        box.add_destroy_button(_("Ok, thanks"))
        self._nc.append(box)

    def _notify_comment_submit(self, app, username, text):
        """
        Notify User about Comment submission with current credentials.
        """
        box = NotificationBox(
            _("You are about to add a <b>comment</b> as <b>%s</b>.") \
                % (escape_markup(username),),
            message_type=Gtk.MessageType.INFO,
            context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)

        def _comment_submit(widget):
            self._comment_submit(app, username, text)
        box.add_button(_("_Ok, cool!"), _comment_submit)

        def _send_comment():
            self._on_send_comment(None, app=app)
        def _logout_webservice(widget):
            self._logout_webservice(app, _send_comment)
        box.add_button(_("_No, logout!"), _logout_webservice)

        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _comment_submit(self, app, username, text):
        """
        Actual Comment submit to Web Service.
        Here we arrive from the MainThread.
        """
        task = ParallelTask(
            self._comment_submit_thread_body,
            app, username, text)
        task.name = "CommentSubmitThreadBody"
        task.daemon = True
        task.start()

    def _comment_submit_thread_body(self, app, username, text):
        """
        Called by _comment_submit(), does the actualy submit.
        """
        repository_id = app.get_details().channelname
        webserv = self._entropy_ws.get(repository_id)
        if webserv is None:
            # impossible!
            return

        key = app.get_details().pkgkey
        doc_factory = webserv.document_factory()
        doc = doc_factory.comment(
            username, text, "", "")

        err_msg = None
        try:
            new_doc = webserv.add_document(key, doc)
        except WebService.WebServiceException as err:
            new_doc = None
            err_msg = str(err)

        def _submit_success(doc):
            box = CommentBox(doc, is_last=True)
            box.render()
            self._app_my_comments_box.pack_start(box, False, False, 2)
            box.show()
            self._app_my_comments_box.show()

            nbox = NotificationBox(
                _("Your comment has been submitted!"),
                message_type=Gtk.MessageType.INFO,
                context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
            nbox.add_destroy_button(_("Ok, great!"))
            self._app_comment_text_buffer.set_text("")
            self._nc.append(nbox, timeout=10)

        def _submit_fail():
            box = NotificationBox(
                _("Comment submit error: <i>%s</i>") % (err_msg,),
                message_type=Gtk.MessageType.ERROR,
                context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
            box.add_destroy_button(_("Ok, thanks"))
            self._nc.append(box)

        if new_doc is not None:
            GLib.idle_add(_submit_success, new_doc)
        else:
            GLib.idle_add(_submit_fail)

    def _logout_webservice(self, app, reinit_callback):
        """
        Execute logout of current credentials from Web Service.
        Actually, this means removing the local cookie.
        """
        repository_id = app.get_details().channelname
        webserv = self._entropy_ws.get(repository_id)
        if webserv is not None:
            webserv.remove_credentials()

        GLib.idle_add(reinit_callback)

    def _notify_login_request(self, app, text, on_success, on_fail,
                              context_id):
        """
        Notify User that login is required
        """
        box = LoginNotificationBox(self._entropy_ws, app)
        box.connect("login-success", on_success)
        box.connect("login-failed", on_fail)
        self._nc.append(box)

    def _on_comment_login_success(self, widget, username, app):
        """
        Notify user that we successfully logged in!
        """
        box = NotificationBox(
            _("Logged in as <b>%s</b>! How about your <b>comment</b>?") \
                % (escape_markup(username),),
            message_type=Gtk.MessageType.INFO,
            context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
        def _send_comment(widget):
            self._on_send_comment(widget, app=app)
        box.add_button(_("_Send now"), _send_comment)
        box.add_destroy_button(_("_Later"))
        self._nc.append(box)

    def _on_comment_login_failed(self, widget, app):
        """
        Entropy Web Services Login failed message.
        """
        box = NotificationBox(
            _("Login failed. Your <b>comment</b> hasn't been added"),
            message_type=Gtk.MessageType.ERROR,
            context_id=self.COMMENT_NOTIFICATION_CONTEXT_ID)
        box.add_destroy_button(_("_Ok, thanks"))
        self._nc.append(box)

    def _append_comments(self, downloader, app, comments, has_more):
        """
        Append given Entropy WebService Document objects to
        the comment area.
        """
        # remove spinner if there, ugly O(n)
        for child in self._app_comments_box.get_children():
            if not isinstance(child, CommentBox):
                child.destroy()

        if not comments:
            label = Gtk.Label()
            label.set_markup(
                _("<i>No <b>comments</b> for this Application, yet!</i>"))
            self._app_comments_box.pack_start(label, False, False, 1)
            label.show()
            return

        if has_more:
            button_box = Gtk.HButtonBox()
            button = Gtk.Button()
            button.set_label(_("Older comments"))
            button.set_alignment(0.5, 0.5)
            def _enqueue_download(widget):
                widget.get_parent().destroy()
                spinner = Gtk.Spinner()
                spinner.set_size_request(24, 24)
                spinner.set_tooltip_text(_("Loading older comments..."))
                spinner.set_name("comment-box-spinner")
                self._app_comments_box.pack_end(spinner, False, False, 3)
                spinner.show()
                downloader.enqueue_download()
            button.connect("clicked", _enqueue_download)

            button_box.pack_start(button, False, False, 0)
            self._app_comments_box.pack_start(button_box, False, False, 1)
            button_box.show_all()

        idx = 0
        length = len(comments)
        for doc in comments:
            idx += 1
            box = CommentBox(doc, is_last=(not has_more and (idx == length)))
            box.render()
            self._app_comments_box.pack_end(box, False, False, 2)
            box.show()

    def _append_comments_safe(self, downloader, app, comments, has_more):
        """
        Same as _append_comments() but thread-safe.
        """
        GLib.idle_add(self._append_comments, downloader, app,
                      comments, has_more)

    def _append_images(self, downloader, app, images, has_more):
        """
        Append given Entropy WebService Document objects to
        the images area.
        """
        # remove spinner if there, ugly O(n)
        for child in self._app_images_box.get_children():
            if not isinstance(child, ImageBox):
                child.destroy()

        if not images:
            label = Gtk.Label()
            label.set_markup(
                _("<i>No <b>images</b> for this Application, yet!</i>"))
            self._app_images_box.pack_start(label, False, False, 1)
            label.show()
            return

        if has_more:
            button_box = Gtk.HButtonBox()
            button = Gtk.Button()
            button.set_label(_("Older images"))
            button.set_alignment(0.5, 0.5)
            def _enqueue_download(widget):
                widget.get_parent().destroy()
                spinner = Gtk.Spinner()
                spinner.set_size_request(24, 24)
                spinner.set_tooltip_text(_("Loading older images..."))
                spinner.set_name("image-box-spinner")
                self._app_images_box.pack_end(spinner, False, False, 3)
                spinner.show()
                downloader.enqueue_download()
            button.connect("clicked", _enqueue_download)

            button_box.pack_start(button, False, False, 0)
            self._app_images_box.pack_start(button_box, False, False, 1)
            button_box.show_all()

        idx = 0
        length = len(images)
        for doc in images:
            idx += 1
            box = ImageBox(doc, is_last=(not has_more and (idx == length)))
            box.render()
            self._app_images_box.pack_end(box, False, False, 2)
            box.show()

    def _append_images_safe(self, downloader, app, comments, has_more):
        """
        Same as _append_images() but thread-safe.
        """
        GLib.idle_add(self._append_images, downloader, app,
                      comments, has_more)

    def _setup_application_stats(self, stats, icon):
        """
        Setup widgets related to Application statistics (and icon).
        """
        total_downloads = stats.downloads_total
        if not total_downloads:
            down_msg = _("Never downloaded")
        else:
            down_msg = ngettext("<small><b>%d</b>\ndownload</small>",
                                "<small><b>%d</b>\ndownloads</small>",
                                total_downloads)
            down_msg = down_msg % (total_downloads,)

        self._app_downloaded_lbl.set_markup(down_msg)
        if icon:
            self._image.set_from_pixbuf(icon)
        self._stars.set_rating(stats.ratings_average)
        self._stars_alignment.show_all()

    def _setup_application_info(self, app, metadata):
        """
        Setup the actual UI widgets content and emit 'application-show'
        """
        self._app_name_lbl.set_markup(metadata['markup'])
        self._app_info_lbl.set_markup(metadata['info'])

        # FIXME, lxnay complete
        # install/remove/update buttons
        

        # only comments supported, point to the remote
        # www service for the rest
        self._app_comment_more_label.set_markup(
            "<b>%s</b>: <a href=\"%s\">%s</a>" % (
                _("Want to add images, etc?"),
                build_application_store_url(app, "ugc"),
                _("click here!"),))

        stats = metadata['stats']
        icon = metadata['icon']
        self._setup_application_stats(stats, icon)

        # load application comments asynchronously
        # so at the beginning, just place a spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(-1, 48)
        spinner.set_tooltip_text(_("Loading comments..."))
        spinner.set_name("comment-box-spinner")
        for child in self._app_comments_box.get_children():
            child.destroy()
        self._app_comments_box.pack_start(spinner, False, False, 0)
        spinner.show()
        spinner.start()

        downloader = ApplicationViewController.MetadataDownloader(
            app, self, self._append_comments_safe,
            app.download_comments)
        downloader.start()

        downloader = ApplicationViewController.MetadataDownloader(
            app, self, self._append_images_safe,
            app.download_images)
        downloader.start()

        self.emit("application-show", app)

    class MetadataDownloader(GObject.Object):
        """
        Automated Application comments downloader.
        """

        def __init__(self, app, avc, callback, app_downloader_method):
            self._app = app
            self._avc = avc
            self._offset = 0
            self._callback = callback
            self._task = ParallelTask(self._download)
            self._app_downloader = app_downloader_method

        def start(self):
            """
            Start downloading comments and send them to callback.
            Loop over until we have more of them to download.
            """
            self._offset = 0
            self._task.start()

        def _download_callback(self, document_list):
            """
            Callback called by download_<something>() once data
            is arrived from web service.
            document_list can be None!
            """
            has_more = 0
            if document_list is not None:
                has_more = document_list.has_more()
            # stash more data?
            if has_more and (document_list is not None):
                self._offset += len(document_list)
                # download() will be called externally

            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "MetadataDownloader._download_callback: %s, more: %s" % (
                        document_list, has_more))
                if document_list is not None:
                    const_debug_write(
                        __name__,
                        "MetadataDownloader._download_callback: "
                            "total: %s, offset: %s" % (
                            document_list.total(), document_list.offset()))

            self._callback(self, self._app, document_list, has_more)

        def reset_offset(self):
            """
            Reset Metadata download offset to 0.
            """
            self._offset = 0

        def get_offset(self):
            """
            Get current Metadata download offset.
            """
            return self._offset

        def enqueue_download(self):
            """
            Enqueue a new download, starting from current offset
            """
            self._task = ParallelTask(self._download)
            self._task.start()

        def _download(self):
            """
            Thread body of the initial Metadata downloader.
            """
            self._app_downloader(self._download_callback,
                                 offset=self._offset)


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

    # Possible Rigo Application UI States
    BROWSER_VIEW_STATE, STATIC_VIEW_STATE, \
        APPLICATION_VIEW_STATE = range(3)

    def __init__(self):
        icons = get_sc_icon_theme(DATA_DIR)

        self._entropy = Client()
        self._entropy_ws = EntropyWebService(self._entropy)

        self._builder = Gtk.Builder()
        self._builder.add_from_file(os.path.join(DATA_DIR, "ui/gtk3/rigo.ui"))
        self._builder.connect_signals(Rigo.RigoHandler())
        self._window = self._builder.get_object("rigoWindow")
        self._window.set_name("rigo-view")
        self._apps_view = self._builder.get_object("appsViewVbox")
        self._scrolled_view = self._builder.get_object("appsViewScrolledWindow")
        self._app_view = self._builder.get_object("appViewScrollWin")
        self._app_view.set_name("rigo-view")
        self._app_view_port = self._builder.get_object("appViewVport")
        self._app_view_port.set_name("rigo-view")
        self._search_entry = self._builder.get_object("searchEntry")
        self._static_view = self._builder.get_object("staticViewVbox")
        self._notification = self._builder.get_object("notificationBox")

        self._app_view_c = ApplicationViewController(
            self._entropy, self._entropy_ws, self._builder)

        self._view = AppTreeView(self._app_view_c, icons, True,
                                 AppListStore.ICON_SIZE, store=None)
        self._scrolled_view.add(self._view)

        self._app_store = AppListStore(
            self._entropy, self._entropy_ws,
            self._view, icons)
        def _queue_draw(*args):
            self._view.queue_draw()
        self._app_store.connect("redraw-request", _queue_draw)

        self._app_view_c.set_store(self._app_store)
        self._app_view_c.connect("application-show",
            self._on_application_show)

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
            Rigo.APPLICATION_VIEW_STATE: (
                self._enter_application_state,
                self._exit_application_state),
        }
        self._state_mutex = Lock()
        self._avc = ApplicationsViewController(
            self._entropy, icons, self._entropy_ws,
            self._search_entry, self._app_store, self._view)

        self._avc.connect("view-cleared", self._on_view_cleared)
        self._avc.connect("view-filled", self._on_view_filled)

        self._nc = NotificationViewController(
            self._entropy, self._entropy_ws,
            self._avc, self._notification)
        self._app_view_c.set_notification_controller(self._nc)

    def _on_view_cleared(self, *args):
        self._change_view_state(Rigo.STATIC_VIEW_STATE)

    def _on_view_filled(self, *args):
        self._change_view_state(Rigo.BROWSER_VIEW_STATE)

    def _on_application_show(self, *args):
        self._change_view_state(Rigo.APPLICATION_VIEW_STATE)

    def _exit_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._apps_view.hide()

    def _enter_browser_state(self):
        """
        Action triggered when UI exits the Application Browser
        state (or mode).
        """
        self._apps_view.show()

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
                                         True, True, 10)
        self._static_view.show()

    def _enter_application_state(self):
        """
        Action triggered when UI enters the Package Information
        state (or mode). Showing application information.
        """
        self._app_view.show()

    def _exit_application_state(self):
        """
        Action triggered when UI exits the Package Information
        state (or mode). Hiding back application information.
        """
        self._app_view.hide()
        self._app_view_c.hide()

    def _change_view_state(self, state):
        """
        Change Rigo Application UI state.
        You can pass a custom widget that will be shown in case
        of static view state.
        """
        with self._state_mutex:
            txc = self._state_transactions.get(state)
            if txc is None:
                raise AttributeError("wrong view state")
            enter_st, exit_st = txc

            current_enter_st, current_exit_st = self._state_transactions.get(
                self._current_state)
            # exit from current state
            current_exit_st()
            # enter the new state
            enter_st()
            self._current_state = state

    def _change_view_state_safe(self, state):
        """
        Thread-safe version of change_view_state().
        """
        def _do_change():
            return self._change_view_state(state)
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

        self._app_view_c.setup()
        self._avc.setup()
        self._nc.setup()
        self._window.show()

    def run(self):
        """
        Run Rigo ;-)
        """
        self._welcome_box.render()
        self._change_view_state(self._current_state)
        GLib.idle_add(self._permissions_setup)

        GLib.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()
        entropy.tools.kill_threads()

if __name__ == "__main__":
    app = Rigo()
    app.run()
