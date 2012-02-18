# Copyright (C) 2010 Canonical
# Copyright (C) 2012 Fabio Erculiani
#
# Authors:
#  Michael Vogt
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

import logging
import os
import time
from collections import deque
from threading import Semaphore, Lock

from gi.repository import GObject

from entropy.const import const_debug_write, const_debug_enabled
from entropy.i18n import _
from entropy.misc import ParallelTask
from entropy.services.client import WebService
from entropy.client.services.interfaces import ClientWebService

from rigo.enums import Icons


LOG = logging.getLogger(__name__)

class ReviewStats(object):

    NO_RATING = 1

    def __init__(self, app):
        self.app = app
        self.ratings_average = None
        self.downloads_total = 0
        self.rating_spread = [0,0,0,0,0]
        self.dampened_rating = 3.00

    def __repr__(self):
        return ("<ReviewStats '%s' ratings_average='%s' downloads_total='%s'"
                " rating_spread='%s' dampened_rating='%s'>" %
                (self.app, self.ratings_average, self.downloads_total,
                self.rating_spread, self.dampened_rating))

class CategoryRowReference:
    """ A simple container for Category properties to be
        displayed in a AppListStore or AppTreeStore
    """

    def __init__(self, untranslated_name, display_name, subcats, pkg_count):
        self.untranslated_name = untranslated_name
        self.display_name = GObject.markup_escape_text(display_name)
        #self.subcategories = subcats
        self.pkg_count = pkg_count
        self.vis_count = pkg_count
        return

class UncategorisedRowRef(CategoryRowReference):

    def __init__(self, untranslated_name=None, display_name=None, pkg_count=0):
        if untranslated_name is None:
            untranslated_name = 'Uncategorised'
        if display_name is None:
            display_name = _("Uncategorized")

        CategoryRowReference.__init__(self,
                                      untranslated_name,
                                      display_name,
                                      None, pkg_count)
        return

class ApplicationMetadata(object):
    """
    This is the Entropy metadata manager for Application objects.
    These object can register their request here, asynchronously
    and get the response when it's ready.
    For example, they can allocate metadata requests, passing
    a callback method that will be called when the data is available.
    """

    @staticmethod
    def start():
        """
        Start asynchronous Entropy Metadata retrieveal.
        """
        ApplicationMetadata._RATING_THREAD.start()
        ApplicationMetadata._ICON_THREAD.start()

    @staticmethod
    def _rating_thread_body():
        """
        Thread executing package rating remote data retrieval.
        """
        request_list = ["vote", "down"]
        return ApplicationMetadata._generic_thread_body(
            "RatingThread", ApplicationMetadata._RATING_SEM,
            ApplicationMetadata._RATING_THREAD_DISCARD_SIGNAL,
            ApplicationMetadata._RATING_THREAD_SLEEP_SECS,
            ApplicationMetadata._RATING_QUEUE,
            ApplicationMetadata._RATING_LOCK,
            ApplicationMetadata._RATING_IN_FLIGHT,
            request_list)

    @staticmethod
    def _icon_thread_body():
        """
        Thread executing package icon remote data retrieval.
        """
        request_list = ["icon"]
        return ApplicationMetadata._generic_thread_body(
            "IconThread", ApplicationMetadata._ICON_SEM,
            ApplicationMetadata._ICON_THREAD_DISCARD_SIGNAL,
            ApplicationMetadata._ICON_THREAD_SLEEP_SECS,
            ApplicationMetadata._ICON_QUEUE,
            ApplicationMetadata._ICON_LOCK,
            ApplicationMetadata._ICON_IN_FLIGHT,
            request_list)

    @staticmethod
    def _generic_thread_body(name, sem, discard_signal, sleep_secs,
                             queue, mutex, in_flight, request_list):
        """
        Thread executing generic (both rating and doc) metadata retrieval.
        """
        while True:
            sem.acquire()
            discard_signal.set(False)
            const_debug_write(__name__,
                "%s, waking up" % (name,))
            # sleep a bit in order to catch more flies
            time.sleep(sleep_secs)
            # now catch the flies
            local_queue = []
            while True:
                try:
                    local_queue.append(queue.popleft())
                except IndexError:
                    # no more items
                    break

            if const_debug_enabled():
                const_debug_write(__name__,
                    "%s, got: %s" % (name, local_queue,))
            if not local_queue:
                continue

            # setup dispatch map
            pkg_key_map = {}
            # and repository map
            repo_map = {}
            ws_map = {}
            for item in local_queue:
                webserv, key, repo_id, cb, ts = item
                obj = pkg_key_map.setdefault((key, repo_id), [])
                obj.append((cb, ts))

                obj = repo_map.setdefault(repo_id, set())
                obj.add(key)
                ws_map[repo_id] = webserv

            request_outcome = {}
            # issue requests
            for repo_id, keys in repo_map.items():

                webserv = ws_map[repo_id]
                request_map = {
                    "vote": webserv.get_votes,
                    "down": webserv.get_downloads,
                    "icon": webserv.get_icons,
                }

                # FIXME: lxnay, who validates this cache?

                for request in request_list:
                    outcome = {}

                    uncached_keys = []
                    for key in keys:
                        try:
                            outcome[(key, repo_id)] = request_map[request](
                                [key], cache=True, cached=True)[key]
                        except WebService.CacheMiss:
                            uncached_keys.append(key)

                    for key in uncached_keys:
                        if discard_signal.get():
                            break
                        try:
                            # FIXME, lxnay: work more instances in parallel?
                            outcome[(key, repo_id)] = request_map[request](
                                [key], cache = True)[key]
                        except WebService.WebServiceException as wse:
                            const_debug_write(
                                __name__,
                                "%s, WebServiceExc: %s" % (name, wse,)
                                )
                            outcome[(key, repo_id)] = None

                    request_outcome[request] = outcome

            # don't worry about races
            if discard_signal.get():
                const_debug_write(
                    __name__,
                    "%s, discard signal received." % (name,)
                )
                discard_signal.set(False)
                request_outcome.clear()
                continue

            # dispatch results
            for (key, repo_id), cb_ts_list in pkg_key_map.items():
                for (cb, ts) in cb_ts_list:
                    with mutex:
                        in_flight.discard((key, repo_id))
                    if cb is not None:
                        outcome_values = []
                        for request in request_list:
                            outcome_values.append(
                                request_outcome[request].get((key, repo_id)))
                        task = ParallelTask(cb, outcome_values, ts)
                        task.name = "%sCb{%s, %s}" % (name, repo_id, key)
                        task.start()

    @staticmethod
    def discard():
        """
        Discard all the queued requests. No longer needed.
        """
        const_debug_write(__name__,
            "ApplicationMetadata.discard() called")
        for th_info in ApplicationMetadata._REGISTERED_THREAD_INFO:
            th, queue, sem, lock, \
                discard_signal, in_flight = th_info
            while True:
                try:
                    queue.popleft()
                    # we could use blocking mode, but no actual need
                    sem.acquire(False)
                except IndexError:
                    break
            with lock:
                in_flight.clear()
            discard_signal.set(True)

    @staticmethod
    def _download_document(entropy_ws, document, cache=True):
        """
        Dowload Document (Icon, File, Image, etc) through the Entropy
        WebService interface.
        Return path to just downloaded Document if success, None otherwise.
        """
        local_path = None
        try:
            local_path = entropy_ws.get_document_url(document,
                cache=cache)
        except ClientWebService.DocumentError as err:
            const_debug_write(__name__,
                "_download_document: document error: %s" % (
                    err,))
        return local_path

    @staticmethod
    def _enqueue_rating(webservice, package_key, repository_id, callback):
        """
        Enqueue the retriveal of the Rating for package key in given repository.
        Once the data is ready, callback() will be called passing the
        payload.
        This method is asynchronous and returns as soon as possible.
        callback() signature is: callback(payload, request_timestamp_float).
        If data is not available, payload will be None.
        callback argument can be None.
        _RATING_LOCK must be acquired by caller.
        """
        if const_debug_enabled():
            const_debug_write(
                __name__,
                "_enqueue_rating: %s, %s" % (package_key, repository_id))
        request_time = time.time()
        in_flight = ApplicationMetadata._RATING_IN_FLIGHT
        queue = ApplicationMetadata._RATING_QUEUE
        sem = ApplicationMetadata._RATING_SEM
        in_flight.add((package_key, repository_id))
        queue.append((webservice, package_key,
                      repository_id, callback, request_time))
        sem.release()

    @staticmethod
    def _enqueue_icon(webservice, package_key, repository_id, callback):
        """
        Enqueue the retrieval of the Icon for package key in given repository.
        Once the data is ready, callback() will be called passing the
        payload.
        This method is asynchronous and returns as soon as possible.
        callback() signature is: callback(payload, request_timestamp_float).
        If data is not available, payload will be None.
        callback argument can be None.
        _ICON_LOCK must be acquired by caller.
        """
        if const_debug_enabled():
            const_debug_write(
                __name__,
                "_enqueue_icon: %s, %s" % (package_key, repository_id))

        request_time = time.time()
        in_flight = ApplicationMetadata._ICON_IN_FLIGHT
        queue = ApplicationMetadata._ICON_QUEUE
        sem = ApplicationMetadata._ICON_SEM
        in_flight.add((package_key, repository_id))
        queue.append((webservice, package_key,
                      repository_id, callback, request_time))
        sem.release()

    @staticmethod
    def lazy_get_rating(entropy_ws, package_key, repository_id,
                        callback=None):
        """
        Return the Rating (stars) for given package key, if it's available
        in local cache. At the same time, if not available and not already
        enqueued for download, do it, atomically.
        Return None if not available, the rating otherwise (tuple composed
        by (vote, number_of_downloads)).
        """
        webserv = entropy_ws.get(repository_id)
        if webserv is None:
            return None

        try:
            vote = webserv.get_votes(
                [package_key], cache=True, cached=True)[package_key]
            down = webserv.get_downloads(
                [package_key], cache=True, cached=True)[package_key]
        except WebService.CacheMiss as exc:
            if const_debug_enabled():
                const_debug_write(__name__,
                    "lazy_get_rating: cache miss for: %s, %s" % (
                        package_key, repository_id))
            # not in cache
            flight_key = (package_key, repository_id)
            with ApplicationMetadata._RATING_LOCK:
                if flight_key not in ApplicationMetadata._RATING_IN_FLIGHT:
                    # enqueue a new rating then
                    ApplicationMetadata._enqueue_rating(
                        webserv, package_key,
                        repository_id, callback)
            # let caller handle this
            raise exc

        return vote, down

    @staticmethod
    def lazy_get_icon(entropy_ws, package_key, repository_id,
                        callback=None):
        """
        Return a DocumentList of Icons for given package key, if it's available
        in local cache. At the same time, if not available and not already
        enqueued for download, do it, atomically.
        Return None if not available, or DocumentList (see Entropy Services
        API) otherwise. DocumentList contains a list of Document objects,
        and calling Document.local_document() would give you the image path.
        """
        webserv = entropy_ws.get(repository_id)
        if webserv is None:
            return None

        def _pick_icon(icons):
            return icons[0]

        def _icon_callback(outcomes, ts):
            icons = outcomes[0]
            if not icons:
                # sadly, no icons
                return
            local_path = ApplicationMetadata._download_document(
                webserv, _pick_icon(icons))
            if local_path:
                # only if successful, otherwise we fall into
                # infinite loop
                callback(icons)

        try:
            icons = webserv.get_icons(
                [package_key], cache=True, cached=True)[package_key]
        except WebService.CacheMiss as exc:
            if const_debug_enabled():
                const_debug_write(__name__,
                    "lazy_get_icon: cache miss for: %s, %s" % (
                        package_key, repository_id))
            # not in cache
            flight_key = (package_key, repository_id)
            with ApplicationMetadata._ICON_LOCK:
                if flight_key not in ApplicationMetadata._ICON_IN_FLIGHT:
                    # enqueue a new rating then
                    ApplicationMetadata._enqueue_icon(
                        webserv, package_key,
                        repository_id, _icon_callback)
            # let caller handle this
            raise exc

        if not icons:
            return None

        # pick the first icon as document icon
        icon = _pick_icon(icons)
        # check if we have the file on-disk, otherwise
        # spawn the fetch in parallel.
        icon_path = icon.local_document()
        if not os.path.isfile(icon_path):
            task = ParallelTask(_icon_callback, [icons], time.time())
            task.daemon = True
            task.name = "FetchIconCb{(%s, %s)}" % ((package_key, repository_id))
            task.start()

        return icon

    class SignalBoolean(object):

        def __init__(self, val):
            self.__val = val

        def set(self, val):
            self.__val = val

        def get(self):
            return self.__val

    # Application Rating logic
    _RATING_QUEUE = deque()
    def _rating_thread_body_wrapper():
        return ApplicationMetadata._rating_thread_body()
    _RATING_THREAD = ParallelTask(_rating_thread_body_wrapper)
    _RATING_THREAD.daemon = True
    _RATING_THREAD.name = "RatingThread"
    _RATING_THREAD_SLEEP_SECS = 1.0
    _RATING_THREAD_DISCARD_SIGNAL = SignalBoolean(False)
    _RATING_SEM = Semaphore(0)
    _RATING_LOCK = Lock()
    _RATING_IN_FLIGHT = set()

    # Application Documents logic
    _ICON_QUEUE = deque()
    def _icon_thread_body_wrapper():
        return ApplicationMetadata._icon_thread_body()
    _ICON_THREAD = ParallelTask(_icon_thread_body_wrapper)
    _ICON_THREAD.daemon = True
    _ICON_THREAD.name = "IconThread"
    _ICON_THREAD_SLEEP_SECS = 0.5
    _ICON_THREAD_DISCARD_SIGNAL = SignalBoolean(False)
    _ICON_SEM = Semaphore(0)
    _ICON_LOCK = Lock()
    _ICON_IN_FLIGHT = set()

    _REGISTERED_THREAD_INFO = [
        # rating
        (_RATING_THREAD, _RATING_QUEUE,
         _RATING_SEM, _RATING_LOCK,
         _RATING_THREAD_DISCARD_SIGNAL,
         _RATING_IN_FLIGHT),
        # icon
        (_ICON_THREAD, _ICON_QUEUE,
         _ICON_SEM, _ICON_LOCK,
         _ICON_THREAD_DISCARD_SIGNAL,
         _ICON_IN_FLIGHT),
    ]


# this is a very lean class as its used in the main listview
# and there are a lot of application objects in memory
class Application(object):
    """
    The central software item abstraction. it contains a
    pkgname that is always available and a optional appname
    for packages with multiple applications
    There is also a __cmp__ method and a name property
    """

    def __init__(self, entropy_client, entropy_ws, package_match,
                 redraw_callback=None):
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._pkg_match = package_match
        self._pkg_id, self._repo_id = package_match
        self._redraw_callback = redraw_callback

    @property
    def name(self):
        """Show user visible name"""
        repo = self._entropy.open_repository(self._repo_id)
        name = repo.retrieveName(self._pkg_id)
        if name is None:
            return _("N/A")
        return name.capitalize()

    def is_installed(self):
        """
        Return if Application is currently installed.
        """
        inst_repo = self._entropy.installed_repository()
        repo = self._entropy.open_repository(self._repo_id)
        if repo is inst_repo:
            return True
        key_slot = repo.retrieveKeySlot(self._pkg_id)
        if key_slot is None:
            return False
        key, slot = key_slot
        matches = inst_repo.searchKeySlot(key, slot)
        if matches:
            return True
        return False

    def is_available(self):
        """
        Return if Application is actually available in repos,
        for cache reasons?
        The actual semantics of this method in softwarecenter
        seems quite ambiguous to me.
        """
        repo = self._entropy.open_repository(self._repo_id)
        return repo.isPackageIdAvailable(self._pkg_id)

    def get_markup(self):
        repo = self._entropy.open_repository(self._repo_id)
        name = repo.retrieveName(self._pkg_id)
        version = repo.retrieveVersion(self._pkg_id)
        if version is None:
            version = "N/A"
        description = repo.retrieveDescription(self._pkg_id)
        if description is None:
            description = _("No description")
        if len(description) > 79:
            description =  description[:80].strip() + "..."
        text = "%s %s\n<small><i>%s</i></small>" % (
            GObject.markup_escape_text(name),
            GObject.markup_escape_text(version),
            GObject.markup_escape_text(description))
        return text

    def get_review_stats(self):
        """
        Return ReviewStats object containing user review
        information about this Application, like
        votes and number of downloads.
        """
        stat = ReviewStats(self)
        stat.ratings_average = ReviewStats.NO_RATING

        repo = self._entropy.open_repository(self._repo_id)
        key_slot = repo.retrieveKeySlot(self._pkg_id)
        if key_slot is None:
            return stat # empty stats
        key, slot = key_slot
        try:
            rating = ApplicationMetadata.lazy_get_rating(
                self._entropy_ws, key, self._repo_id,
                callback=self._redraw_callback)
        except WebService.CacheMiss:
            # not in cache, return empty stats
            return stat

        if rating is None:
            # not ready yet, return empty ratings
            return stat # empty stats
        vote, down = rating
        if vote is not None:
            stat.ratings_average = vote
        if down is not None:
            # otherwise 0 is shown
            stat.downloads_total = down
        return stat

    # get a AppDetails object for this Applications
    def get_details(self):
        """
        Return a new AppDetails object for this application
        """
        return AppDetails(self._entropy, self._entropy_ws,
                          self._pkg_match, self,
                          redraw_callback=self._redraw_callback)

    def __str__(self):
        repo = self._entropy.open_repository(self._repo_id)
        atom = repo.retrieveAtom(self._pkg_id)
        return "(%s: %s)" % (self._pkg_match, atom)

    def __repr__(self):
        return str(self)


# the details
class AppDetails(object):
    """
    The details for a Application. This contains all the information
    we have available like website etc
    """

    def __init__(self, entropy_client, entropy_ws, package_match, app,
                 redraw_callback=None):
        """
        Create a new AppDetails object.
        """
        self._entropy = entropy_client
        self._entropy_ws = entropy_ws
        self._pkg_match = package_match
        self._pkg_id, self._repo_id = package_match
        self._app = app
        self._redraw_callback = redraw_callback

    @property
    def channelname(self):
        return self._repo_id

    @property
    def eulafile(self):
        """Return path to the EULA for App"""
        # or None

    @property
    def desktop_file(self):
        """Return path (?) to desktop file"""
        # FIXME, we should have it

    @property
    def description(self):
        repo = self._entropy.open_repository(self._repo_id)
        return repo.retrieveDescription(self._pkg_id)

    @property
    def error(self):
        return _("Application not found")

    @property
    def icon(self):
        """
        Return Application Icon image Entropy Document object.
        In case of missing icon, None is returned.
        The actual outcome of this property is a tuple, composed
        by the Document object (or None) and cache hit information
        (True if got from local cache, False if not in local cache)
        """
        repo = self._entropy.open_repository(self._repo_id)
        key_slot = repo.retrieveKeySlot(self._pkg_id)
        if key_slot is None:
            return None, False

        key, slot = key_slot
        cache_hit = True
        try:
            icon = ApplicationMetadata.lazy_get_icon(
                self._entropy_ws, key, self._repo_id,
                callback=self._redraw_callback)
        except WebService.CacheMiss:
            cache_hit = False
            icon = None

        if const_debug_enabled():
            const_debug_write(__name__,
                "AppDetails{%s}.icon: icon: %s, cache hit: %s" % (
                    self._pkg_match,
                    icon, cache_hit))

        return icon, cache_hit

    @property
    def icon_file_name(self):
        """Return icon file name for package"""
        # FIXME, we have it

    @property
    def icon_url(self):
        """Return icon download URL"""
        # FIXME, we have it

    @property
    def cached_icon_file_path(self):
        """Return path to cached icon (downloaded?) if we have it"""
        # FIXME, we have it

    @property
    def installation_date(self):
        repo = self._entropy.open_repository(self._repo_id)
        return entropy.tools.convert_unix_time_to_human_time(
            float(repo.retrieveCreationDate(self._pkg_id)))

    @property
    def purchase_date(self):
        return self.installation_date

    @property
    def license(self):
        repo = self._entropy.open_repository(self._repo_id)
        return repo.retrieveLicenseText(self._pkg_id)

    @property
    def name(self):
        """ Return the name of the application, this will always
            return Application.name. Most UI will want to use
            the property display_name instead
        """
        return self._app.name

    @property
    def display_name(self):
        """ Return the application name as it should be displayed in the UI
            If the appname is defined, just return it, else return
            the summary (per the spec)
        """
        # FIXME, do we want anything different?
        return self.name

    @property
    def display_summary(self):
        """ Return the application summary as it should be displayed in the UI
            If the appname is defined, return the application summary, else return
            the application's pkgname (per the spec)
        """
        # FIXME, is description allrite?
        return self.description

    @property
    def pkg(self):
        return self._pkg_match

    @property
    def pkgname(self):
        return self.name

    @property
    def signing_key_id(self):
        return self._repo_id

    @property
    def screenshot(self):
        # FIXME, what should we do here? use UGC image metadata?
        return None

    @property
    def summary(self):
        return self.description
        # FIXME, return long description? localized desc?

    @property
    def thumbnail(self):
        """Thumbnail for the screenshot"""
        # FIXME, I think we don't have it
        return None

    @property
    def version(self):
        repo = self._entropy.open_repository(self._repo_id)
        # FIXME, also return tag?
        return repo.retrieveVersion(self._pkg_id)

    @property
    def website(self):
        repo = self._entropy.open_repository(self._repo_id)
        return repo.retrieveHomepage(self._pkg_id)

    def __str__(self):
        details = []
        details.append("* AppDetails")
        details.append("                name: %s" % self.name)
        details.append("        display_name: %s" % self.display_name)
        details.append("                 pkg: %s" % self.pkg)
        details.append("             pkgname: %s" % self.pkgname)
        details.append("         channelname: %s" % self.channelname)
        details.append("        desktop_file: %s" % self.desktop_file)
        details.append("         description: %s" % self.description)
        details.append("               error: %s" % self.error)
        details.append("                icon: %s" % self.icon)
        details.append("      icon_file_name: %s" % self.icon_file_name)
        details.append("            icon_url: %s" % self.icon_url)
        details.append("   installation_date: %s" % self.installation_date)
        details.append("       purchase_date: %s" % self.purchase_date)
        details.append("             license: %s" % self.license)
        details.append("          screenshot: %s" % self.screenshot)
        details.append("             summary: %s" % self.summary)
        details.append("     display_summary: %s" % self.display_summary)
        details.append("           thumbnail: %s" % self.thumbnail)
        details.append("             version: %s" % self.version)
        details.append("             website: %s" % self.website)
        return '\n'.join(details)
