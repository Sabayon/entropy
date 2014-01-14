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

from gi.repository import Gtk, Gdk, GLib, GObject

from rigo.em import StockEms
from rigo.enums import AppActions, RigoViewStates
from rigo.ui.gtk3.widgets.notifications import NotificationBox, \
    LoginNotificationBox
from rigo.ui.gtk3.widgets.stars import ReactiveStar
from rigo.ui.gtk3.widgets.comments import CommentBox
from rigo.ui.gtk3.widgets.images import ImageBox
from rigo.utils import build_application_store_url, \
    escape_markup, prepare_markup
from rigo.models.preference import Preference

from RigoDaemon.enums import AppActions as DaemonAppActions, \
    ActivityStates as DaemonActivityStates

from entropy.const import etpConst, const_debug_write, \
    const_debug_enabled, const_convert_to_unicode, const_isunicode
from entropy.services.client import WebService
from entropy.misc import ParallelTask
from entropy.i18n import _, ngettext

import entropy.tools

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
                                         GObject.TYPE_PYOBJECT),
                                       ),
    }

    VOTE_NOTIFICATION_CONTEXT_ID = "VoteNotificationContext"
    COMMENT_NOTIFICATION_CONTEXT_ID = "CommentNotificationContext"

    def __init__(self, entropy_client, entropy_ws, prefc,
                 rigo_service, builder):
        GObject.Object.__init__(self)
        self._builder = builder
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._service = rigo_service
        self._prefc = prefc
        self._app_store = None
        self._last_app = None
        self._nc = None
        self._avc = None
        self._visible = False

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
        self._app_button_area = self._builder.get_object("appViewButtonArea")

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

    def set_applications_controller(self, avc):
        """
        Bind ApplicationsViewController object to this class.
        """
        self._avc = avc

    def set_store(self, store):
        """
        Bind AppListStore object to this class.
        """
        self._app_store = store

    def setup(self):

        pref = Preference(
            50,
            _("Clean Entropy Web Service Session"),
            _("Discard any registered login credential "
              "used to send votes and comments."),
            "edit-clear", self._logout)
        self._prefc.append(pref)

        self.connect(
            "application-activated",
            self._on_application_activated)
        self._app_store.connect(
            "redraw-request", self._on_redraw_request)
        self._app_comment_send_button.connect(
            "clicked", self._on_send_comment)
        self._app_comment_send_button.set_sensitive(False)
        self._app_comment_text_buffer.connect(
            "changed", self._on_comment_buffer_changed)
        self._stars.connect("changed", self._on_stars_clicked)
        self._app_info_lbl.connect(
            "activate-link", self._on_info_lbl_activate_link)

        self._service.connect(
            "application-processed", self._on_reload_state)
        self._service.connect(
            "application-processing", self._on_reload_state)
        self._service.connect(
            "application-abort", self._on_reload_state)

    def _get_app_transaction(self, app):
        """
        Get Application transaction state (AppAction enum).
        """
        pkg_match = app.get_details().pkg
        local_txs = self._service.local_transactions()
        tx = local_txs.get(pkg_match)
        if tx is None:
            tx = self._service.action(app)
            if tx == DaemonAppActions.IDLE:
                tx = None
        return tx

    def _on_reload_state(self, srv, app, daemon_action, app_outcome=None):
        """
        Reload Application state due to a transaction event.
        """
        if not self._visible:
            return
        last_app = self._last_app
        if last_app is not None:
            app = last_app
        task = ParallelTask(self._reload_application_state, app)
        task.daemon = True
        task.name = "OnReloadAppState"
        task.start()

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
        self._visible = True
        self._last_app = app
        task = ParallelTask(self.__application_activate, app)
        task.name = "ApplicationActivate"
        task.daemon = True
        task.start()

    def _on_info_lbl_activate_link(self, widget, uri):
        """
        Event coming from Application Information label on link
        clicked.
        """
        if uri.startswith("app://"):
            if self._avc is not None:
                self._avc.search(uri[len("app://"):])
            return True
        return False

    def _on_redraw_request(self, widget, pkg_match):
        """
        Redraw request received from AppListStore for given package match.
        We are required to update rating, number of downloads, icon.
        """
        if self._last_app is None:
            return

        if pkg_match == self._last_app.get_details().pkg:
            app = self._app_store.get_application(pkg_match)

            def _still_visible():
                return self._app_store.visible(pkg_match)
            stats = app.get_review_stats(_still_visible_cb=_still_visible)

            icon = self._app_store.get_icon(app)
            self._setup_application_stats(stats, icon)
            if self._app_store is not None:
                self._app_store.emit("redraw-request", self._app_store)

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
        msg = ngettext("Rate <b>%s</b> as <b>%s</b>, with <b>%d</b> star?",
                       "Rate <b>%s</b> as <b>%s</b>, with <b>%d</b> stars?",
                       vote)
        msg = msg % (app.name, escape_markup(username), vote,)
        box = NotificationBox(msg,
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
        metadata['icon'] = self._app_store.get_icon(app)
        metadata['is_installed'] = app.is_installed()
        metadata['is_updatable'] = app.is_updatable()
        GLib.idle_add(self._setup_application_info, app, metadata)

    def hide(self):
        """
        This method shall be called when the Controller widgets are
        going to hide.
        """
        self._visible = False
        self._last_app = None
        for child in self._app_my_comments_box.get_children():
            child.destroy()
        for child in self._app_images_box.get_children():
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
        text = const_convert_to_unicode(text, enctype=etpConst['conf_encoding'])

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
            box = CommentBox(self._nc, self._avc, webserv, doc, is_last=True)
            box.connect("destroy", self._on_comment_box_destroy)

            self.__clean_my_non_comment_boxes()
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

    def _logout(self):
        """
        Logout from any configured repository.
        """
        with self._entropy.rwsem().reader():
            repositories = self._entropy.repositories()

        for repository in repositories:
            webserv = self._entropy_ws.get(repository)
            if webserv is not None:
                webserv.remove_credentials()

        GLib.idle_add(self._avc.emit, "logged-out")
        GLib.idle_add(self._avc.emit, "view-want-change",
                      RigoViewStates.STATIC_VIEW_STATE,
                      None)

    def _logout_webservice(self, app, reinit_callback):
        """
        Execute logout of current credentials from Web Service.
        Actually, this means removing the local cookie.
        """
        repository_id = app.get_details().channelname
        webserv = self._entropy_ws.get(repository_id)
        if webserv is not None:
            webserv.remove_credentials()

        GLib.idle_add(self._avc.emit, "logged-out")
        GLib.idle_add(reinit_callback)

    def _notify_login_request(self, app, text, on_success, on_fail,
                              context_id):
        """
        Notify User that login is required
        """
        box = LoginNotificationBox(
            self._avc, self._entropy_ws, app,
            context_id=context_id)
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

    def _on_comment_box_destroy(self, widget):
        """
        Called when a CommentBox is destroyed.
        We need to figure out if there are CommentBoxes left and in case
        show the "no comments available" message.
        """
        children = self._app_comments_box.get_children()
        if not children:
            self.__show_no_comments()

    def __show_no_comments(self):
        """
        Create "No comments for this Application" message.
        """
        label = Gtk.Label()
        label.set_markup(
            prepare_markup(
                _("<i>No <b>comments</b> for this Application, yet!</i>")))
        # place in app_my, this way it will get cleared out
        # once a new comment is inserted
        self._app_my_comments_box.pack_start(label, False, False, 1)
        self._app_my_comments_box.show_all()

    def __clean_non_comment_boxes(self):
        """
        Remove children that are not CommentBox objects from
        self._app_comments_box
        """
        for child in self._app_comments_box.get_children():
            if not isinstance(child, CommentBox):
                child.destroy()

    def __clean_my_non_comment_boxes(self):
        """
        Remove children that are not CommentBox objects from
        self._app_my_comments_box
        """
        for child in self._app_my_comments_box.get_children():
            if not isinstance(child, CommentBox):
                child.destroy()

    def __clean_non_image_boxes(self):
        """
        Remove children that are not ImageBox objects from
        self._app_images_box
        """
        for child in self._app_images_box.get_children():
            if not isinstance(child, ImageBox):
                child.destroy()

    def _append_comments(self, downloader, app, comments, has_more):
        """
        Append given Entropy WebService Document objects to
        the comment area.
        """
        self.__clean_non_comment_boxes()
        # make sure we didn't leave stuff here as well
        self.__clean_my_non_comment_boxes()

        if not comments:
            self.__show_no_comments()
            return

        if has_more:
            button_box = Gtk.HButtonBox()
            button = Gtk.Button()
            button.set_label(_("Older comments"))
            button.set_alignment(0.5, 0.5)
            def _enqueue_download(widget):
                widget.get_parent().destroy()
                spinner = Gtk.Spinner()
                spinner.set_size_request(StockEms.XXLARGE,
                                         StockEms.XXLARGE)
                spinner.set_tooltip_text(_("Loading older comments..."))
                spinner.set_name("comment-box-spinner")
                self._app_comments_box.pack_end(spinner, False, False, 3)
                spinner.show()
                spinner.start()
                downloader.enqueue_download()
            button.connect("clicked", _enqueue_download)

            button_box.pack_start(button, False, False, 0)
            self._app_comments_box.pack_start(button_box, False, False, 1)
            button_box.show_all()

        idx = 0
        length = len(comments)
        # can be None
        webserv = self._entropy_ws.get(app.get_details().channelname)
        for doc in comments:
            idx += 1
            box = CommentBox(
                self._nc, self._avc, webserv, doc,
                is_last=(not has_more and (idx == length)))
            box.connect("destroy", self._on_comment_box_destroy)
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
        self.__clean_non_image_boxes()

        if not images:
            label = Gtk.Label()
            label.set_markup(
                prepare_markup(
                    _("<i>No <b>images</b> for this Application, yet!</i>")))
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
                spinner.start()
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

    def _on_app_remove(self, widget, app):
        """
        Remove the given Application.
        """
        inst_app = app.get_installed()
        self.emit("application-request-action",
                  inst_app, AppActions.REMOVE)
        if app.get_details().pkg == inst_app.get_details().pkg:
            # on remove, we should return back to browser view
            # if the Application shown is being removed
            self._avc.emit(
                "view-want-change",
                RigoViewStates.STATIC_VIEW_STATE,
                None)

    def _on_app_install(self, widget, app):
        """
        Install (or reinstall) the given Application.
        """
        self.emit("application-request-action",
                  app, AppActions.INSTALL)

    def _setup_buttons(self, app, is_installed, is_updatable):
        """
        Setup Application View Buttons (Install/Remove/Update).
        """
        button_area = self._app_button_area
        for child in button_area.get_children():
            child.destroy()

        daemon_action = self._get_app_transaction(app)
        daemon_activity = self._service.activity()

        if daemon_activity == DaemonActivityStates.UPGRADING_SYSTEM:
            # If we are upgrading the system, do not show any buttons
            const_debug_write(
                __name__, "system is being upgraded, hide buttons")
            pass
        elif daemon_action is not None:
            button = Gtk.Button()
            if daemon_action == DaemonAppActions.INSTALL:
                button.set_label(escape_markup("Installing"))
            elif daemon_action == DaemonAppActions.REMOVE:
                button.set_label(escape_markup("Removing"))
            button.set_sensitive(False)
            button_area.pack_start(
                button, False, False, 0)
        else:
            if is_installed:
                if is_updatable:
                    update_button = Gtk.Button()
                    update_button.set_label(
                        escape_markup(_("Update")))
                    def _on_app_update(widget):
                        return self._on_app_install(widget, app)
                    update_button.connect("clicked",
                                          _on_app_update)
                    button_area.pack_start(update_button,
                                           False, False, 0)
                else:
                    reinstall_button = Gtk.Button()
                    reinstall_button.set_label(
                        escape_markup(_("Reinstall")))
                    def _on_app_reinstall(widget):
                        return self._on_app_install(widget, app)
                    reinstall_button.connect("clicked",
                                             _on_app_reinstall)
                    button_area.pack_start(reinstall_button,
                                           False, False, 0)

                remove_button = Gtk.Button()
                remove_button.set_label(
                    escape_markup(_("Remove")))
                def _on_app_remove(widget):
                    return self._on_app_remove(widget, app)
                remove_button.connect("clicked", _on_app_remove)
                button_area.pack_start(remove_button,
                                       False, False, 0)

            else:
                install_button = Gtk.Button()
                install_button.set_label(
                    escape_markup(_("Install")))
                def _on_app_install(widget):
                    return self._on_app_install(widget, app)
                install_button.connect("clicked", _on_app_install)
                button_area.pack_start(install_button,
                                       False, False, 0)

        button_area.show_all()

    def _setup_application_stats(self, stats, icon):
        """
        Setup widgets related to Application statistics (and icon).
        """
        total_downloads = stats.downloads_total
        if total_downloads < 0:
            down_msg = escape_markup(_("Not available"))
        elif not total_downloads:
            down_msg = escape_markup(_("Never downloaded"))
        else:
            down_msg = "<small><b>%s</b> %s</small>" % (
                stats.downloads_total_markup,
                escape_markup(_("downloads")),)

        self._app_downloaded_lbl.set_markup(down_msg)
        if icon:
            self._image.set_from_pixbuf(icon)
        self._stars.set_rating(stats.ratings_average)
        self._stars_alignment.show_all()

    def _reload_application_state(self, app):
        """
        Reload Application state after transaction.
        """
        is_installed = app.is_installed()
        is_updatable = app.is_updatable()

        def _setup():
            self._setup_buttons(
                app, is_installed, is_updatable)
            # contains Application Version
            self._setup_application_markup(
                app.get_extended_markup())
        GLib.idle_add(_setup)

    def _setup_application_markup(self, extended_markup):
        """
        Setup Application header text
        """
        self._app_name_lbl.set_markup(extended_markup)

    def _setup_application_info(self, app, metadata):
        """
        Setup the actual UI widgets content and emit 'application-show'
        """
        self._setup_application_markup(metadata['markup'])
        self._app_info_lbl.set_markup(metadata['info'])

        # install/remove/update buttons
        self._setup_buttons(
            app, metadata['is_installed'],
            metadata['is_updatable'])

        # only comments supported, point to the remote
        # www service for the rest
        if app.is_installed_app():
            self._app_comment_more_label.hide()
        else:
            self._app_comment_more_label.set_markup(
                "<b>%s</b>: <a href=\"%s\">%s</a>" % (
                    escape_markup(_("Want to add images, etc?")),
                    escape_markup(build_application_store_url(app, "ugc")),
                    escape_markup(_("click here!")),))
            self._app_comment_more_label.show()

        stats = metadata['stats']
        icon = metadata['icon']
        self._setup_application_stats(stats, icon)

        # load application comments asynchronously
        # so at the beginning, just place a spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(-1, 48)
        spinner.set_tooltip_text(escape_markup(_("Loading comments...")))
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
                            "has_more: %s, offset: %s" % (
                            document_list.has_more(),
                            document_list.offset()))

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
