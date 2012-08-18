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
import hashlib
import errno
import tempfile

from gi.repository import GObject, GLib

from rigo.paths import CONF_DIR
from rigo.ui.gtk3.widgets.notifications import \
    NoticeBoardNotificationBox
from rigo.enums import RigoViewStates
from rigo.utils import open_url

from entropy.cache import EntropyCacher
from entropy.const import etpConst

import entropy.tools


class NoticeBoardViewController(GObject.Object):

    LAST_NOTICES_DIR = os.path.join(CONF_DIR, "last_notices")
    LAST_NOTICES_CACHE_KEY = "last_hash"

    def __init__(self, notice_store, notice_view):
        GObject.Object.__init__(self)
        self._store = notice_store
        self._view = notice_view
        self._cacher = EntropyCacher()
        self._nc = None
        self._avc = None

    def _ensure_cache_dir(self):
        """
        Make sure the cache directory is available.
        """
        path = self.LAST_NOTICES_DIR
        try:
            os.makedirs(path)
        except OSError as err:
            if err.errno == errno.EEXIST:
                if os.path.isfile(path):
                    os.remove(path) # fail, yeah
                return
            elif err.errno == errno.ENOTDIR:
                # wtf? we will fail later for sure
                return
            elif err.errno == errno.EPERM:
                # meh!
                return
            raise

    def _load_last_hash(self):
        """
        Return last notices hash.
        """
        self._ensure_cache_dir()
        data = self._cacher.pop(
            self.LAST_NOTICES_CACHE_KEY,
            cache_dir=self.LAST_NOTICES_DIR)
        return data

    def _store_last_hash(self, last_hash):
        """
        Store the last notices hash to disk.
        """
        self._ensure_cache_dir()
        self._cacher.save(
            self.LAST_NOTICES_CACHE_KEY,
            last_hash,
            cache_dir=self.LAST_NOTICES_DIR)

    def _hash(self, notices):
        """
        Hash a list of Notice objects
        """
        m = hashlib.md5()
        m.update("")
        for notice in notices:
            m.update(notice.hash())
        return m.hexdigest()

    def setup(self):
        """
        Setup the ConfigUpdatesViewController resources.
        """
        self._view.set_model(self._store)
        self._view.connect("show-notice", self._on_show_notice)
        self._view.show()

    def set_notification_controller(self, nc):
        """
        Bind a UpperNotificationViewController to this class.
        """
        self._nc = nc

    def set_applications_controller(self, avc):
        """
        Bind an ApplicationsViewController object to this class.
        """
        self._avc = avc

    def clear(self):
        """
        Clear Configuration Updates
        """
        self._view.clear_model()

    def append(self, opaque):
        """
        Add a ConfigUpdate object to the store.
        """
        self._store.append([opaque])

    def append_many(self, opaque_list):
        """
        Append many ConfigUpdate objects to the store.
        """
        for opaque in opaque_list:
            self._store.append([opaque])

    def set_many(self, opaque_list, _from_search=None):
        """
        Set a new list of ConfigUpdate objects on the store.
        """
        self._view.clear_model()
        self.append_many(opaque_list)

    def clear_safe(self):
        """
        Thread-safe version of clear()
        """
        GLib.idle_add(self.clear)

    def append_safe(self, opaque):
        """
        Thread-safe version of append()
        """
        GLib.idle_add(self.append, opaque)

    def append_many_safe(self, opaque_list):
        """
        Thread-safe version of append_many()
        """
        GLib.idle_add(self.append_many, opaque_list)

    def set_many_safe(self, opaque_list):
        """
        Thread-safe version of set_many()
        """
        GLib.idle_add(self.set_many, opaque_list)

    def notify_notices(self, notices, force=False):
        """
        Notify Configuration File Updates to User.
        """
        if self._nc is not None and self._avc is not None:

            # sort by date
            notices = sorted(notices, key=lambda x: x.parsed_date(),
                             reverse=True)

            current_hash = self._hash(notices)
            last_hash = self._load_last_hash()
            if current_hash == last_hash and not force:
                return

            self.set_many(notices)

            def _nb_let_me_see(widget):
                self._avc.emit(
                    "view-want-change",
                    RigoViewStates.NOTICEBOARD_VIEW_STATE,
                    None)
            def _nb_stop_annoying(widget):
                self._nc.remove(widget)
                self._store_last_hash(current_hash)

            box = NoticeBoardNotificationBox(self._avc, len(notices))
            box.connect("let-me-see", _nb_let_me_see)
            box.connect("stop-annoying", _nb_stop_annoying)
            self._nc.append(box)

    def _on_show_notice(self, view, notice):
        tmp_fd, tmp_path = None, None
        try:
            fname = notice.title().replace("/", "-")
            tmp_fd, tmp_path = tempfile.mkstemp(prefix=fname, suffix=".html")
            with entropy.tools.codecs_fdopen(
                tmp_fd, "w", etpConst['conf_encoding']) as tmp_f:
                tmp_f.write("<b>")
                tmp_f.write(notice.title())
                tmp_f.write("</b>")
                tmp_f.write("\n<br/><i>")
                tmp_f.write(notice.date())
                tmp_f.write("</i>, ")
                tmp_f.write(notice.repository())
                tmp_f.write("\n\n<br/><br/><div style='max-width: 400px'>")
                tmp_f.write(notice.description())
                tmp_f.write("</div>\n\n<br/>")
                tmp_f.write("<b>URL</b>: <a href=\"")
                tmp_f.write(notice.link())
                tmp_f.write("\">")
                tmp_f.write(notice.link())
                tmp_f.write("</a>")
                tmp_f.write("\n<br/><br/>")
                tmp_f.flush()
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            # leaks, but xdg-open is async

        if tmp_path is not None:
            open_url(tmp_path)
