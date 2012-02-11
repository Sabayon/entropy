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

from rigo.utils import get_entropy_webservice

LOG = logging.getLogger(__name__)

class ReviewStats(object):

    NO_RATING = 1

    def __init__(self, app):
        self.app = app
        self.ratings_average = None
        self.ratings_total = 0
        self.rating_spread = [0,0,0,0,0]
        self.dampened_rating = 3.00

    def __repr__(self):
        return ("<ReviewStats '%s' ratings_average='%s' ratings_total='%s'"
                " rating_spread='%s' dampened_rating='%s'>" %
                (self.app, self.ratings_average, self.ratings_total,
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

    @staticmethod
    def _rating_thread_body():
        """
        Thread executing package rating remote data retrieval.
        """
        while True:
            ApplicationMetadata._RATING_SEM.acquire()
            ApplicationMetadata._RATING_THREAD_DISCARD_SIGNAL = False
            const_debug_write(__name__,
                "_rating_thread_body, waking up")
            # sleep a bit in order to catch more flies
            time.sleep(ApplicationMetadata._RATING_THREAD_SLEEP_SECS)
            # now catch the flies
            local_queue = []
            while True:
                try:
                    local_queue.append(
                        ApplicationMetadata._RATING_QUEUE.popleft())
                except IndexError:
                    # no more items
                    break

            if const_debug_enabled():
                const_debug_write(__name__,
                    "_rating_thread_body, got: %s" % (local_queue,))
            if not local_queue:
                continue

            entropy_client = local_queue[0][0]
            # setup dispatch map
            pkg_key_map = {}
            # and repository map
            repo_map = {}
            for item in local_queue:
                _client, key, repo_id, cb, ts = item
                obj = pkg_key_map.setdefault((key, repo_id), [])
                obj.append((cb, ts))

                obj = repo_map.setdefault(repo_id, set())
                obj.add(key)

            votes_map = {}
            downloads_map = {}
            # issue requests
            for repo_id, keys in repo_map.items():

                webserv = ApplicationMetadata._get_webservice(
                    entropy_client, repo_id)
                if webserv is None:
                    continue

                # FIXME: lxnay, who validates this cache?

                uncached_keys = []
                for key in keys:
                    try:
                        votes_map[(key, repo_id)] = webserv.get_votes(
                            [key], cache=True, cached=True)[key]
                    except WebService.CacheMiss:
                        uncached_keys.append(key)

                for key in uncached_keys:
                    if ApplicationMetadata._RATING_THREAD_DISCARD_SIGNAL:
                        break
                    try:
                        # FIXME, lxnay: work more instances in parallel?
                        votes_map[(key, repo_id)] = webserv.get_votes(
                            [key], cache = True)[key]
                    except WebService.WebServiceException as wse:
                        const_debug_write(
                            __name__,
                            "_rating_thread_body, WebServiceExc: %s" % (wse,))
                        votes_map[(key, repo_id)] = None

                uncached_keys = []
                for key in keys:
                    try:
                        downloads_map[(key, repo_id)] = webserv.get_downloads(
                            [key], cache=True, cached=True)[key]
                    except WebService.CacheMiss:
                        uncached_keys.append(key)

                for key in uncached_keys:
                    if ApplicationMetadata._RATING_THREAD_DISCARD_SIGNAL:
                        break
                    try:
                        # FIXME, lxnay: work more instances in parallel?
                        downloads_map[(key, repo_id)] = webserv.get_downloads(
                            [key], cache = True)[key]
                    except WebService.WebServiceException as wse:
                        const_debug_write(
                            __name__,
                            "_rating_thread_body, WebServiceExc: %s" % (wse,))
                        downloads_map[(key, repo_id)] = None

            if ApplicationMetadata._RATING_THREAD_DISCARD_SIGNAL:
                ApplicationMetadata._RATING_THREAD_DISCARD_SIGNAL = False
                continue

            # dispatch results
            for (key, repo_id), cb_ts_list in pkg_key_map.items():
                for (cb, ts) in cb_ts_list:
                    with ApplicationMetadata._RATING_LOCK:
                        ApplicationMetadata._RATING_IN_FLIGHT.discard(
                            (key, repo_id))
                    if cb is not None:
                        vote = votes_map.get((key, repo_id))
                        down = downloads_map.get((key, repo_id))
                        task = ParallelTask(cb, (vote, down), ts)
                        task.name = "RatingThreadCb{%s, %s}" % (repo_id, key)
                        task.start()

    @staticmethod
    def _get_webservice(entropy_client, repository_id):
        """
        Get Entropy WebService object for repository
        """
        webserv = ApplicationMetadata._WEBSERV_CACHE.get(repository_id)

        if webserv == -1:
            return None # not available
        if webserv is not None:
            return webserv

        try:
            webserv = get_entropy_webservice(entropy_client, repository_id)
        except WebService.UnsupportedService:
            ApplicationMetadata._WEBSERV_CACHE[repository_id] = -1
            return None

        ApplicationMetadata._WEBSERV_CACHE[repository_id] = webserv
        return webserv

    @staticmethod
    def discard():
        """
        Discard all the queued requests. No longer needed.
        """
        const_debug_write(__name__,
            "!!! ApplicationMetadata.discard() called !!!")
        while True:
            try:
                ApplicationMetadata._RATING_QUEUE.popleft()
                # we could use blocking mode, but no actual need
                ApplicationMetadata._RATING_SEM.acquire(False)
            except IndexError:
                break
        with ApplicationMetadata._RATING_LOCK:
            ApplicationMetadata._RATING_IN_FLIGHT.clear()
        ApplicationMetadata._RATING_THREAD_DISCARD_SIGNAL = True

    @staticmethod
    def enqueue_rating(entropy_client, package_key, repository_id, callback):
        """
        Enqueue the Rating (stars) for package key in given repository.
        Once the data is ready, callback() will be called passing the
        payload.
        This method is asynchronous and returns as soon as possible.
        callback() signature is: callback(payload, request_timestamp_float).
        If data is not available, payload will be None.
        callback argument can be None.
        """
        request_time = time.time()
        ApplicationMetadata._RATING_IN_FLIGHT.add((package_key, repository_id))
        ApplicationMetadata._RATING_QUEUE.append((entropy_client, package_key,
                             repository_id, callback, request_time))
        ApplicationMetadata._RATING_SEM.release()

    @staticmethod
    def lazy_get_rating(entropy_client, package_key, repository_id,
                        callback=None):
        """
        Return the Rating (stars) for given package key, if it's available
        in local cache. At the same time, if not available and not already
        enqueued for download, do it, atomically.
        Return None if not available, the rating otherwise (tuple composed
        by (vote, number_of_downloads)).
        """
        webserv = ApplicationMetadata._get_webservice(
            entropy_client, repository_id)
        if webserv is None:
            return None

        try:
            vote = webserv.get_votes(
                [package_key], cache=True, cached=True)[package_key]
            down = webserv.get_downloads(
                [package_key], cache=True, cached=True)[package_key]
        except WebService.CacheMiss:
            # not in cache
            flight_key = (package_key, repository_id)
            with ApplicationMetadata._RATING_LOCK:
                if flight_key not in ApplicationMetadata._RATING_IN_FLIGHT:
                    # enqueue a new rating then
                    ApplicationMetadata.enqueue_rating(
                        entropy_client, package_key,
                        repository_id, callback)
            vote = None
            down = None

        return vote, down


    _RATING_QUEUE = deque()
    def _rating_thread_body_wrapper():
        return ApplicationMetadata._rating_thread_body()
    _RATING_THREAD = ParallelTask(_rating_thread_body_wrapper)
    _RATING_THREAD.daemon = True
    _RATING_THREAD.name = "RatingThread"
    _RATING_THREAD_SLEEP_SECS = 1.5
    _RATING_THREAD_DISCARD_SIGNAL = False
    _RATING_SEM = Semaphore(0)
    _RATING_LOCK = Lock()
    _RATING_IN_FLIGHT = set()

    _WEBSERV_CACHE = {}


# this is a very lean class as its used in the main listview
# and there are a lot of application objects in memory
class Application(object):
    """
    The central software item abstraction. it contains a
    pkgname that is always available and a optional appname
    for packages with multiple applications
    There is also a __cmp__ method and a name property
    """

    def __init__(self, entropy_client, package_match, redraw_callback=None):
        self._entropy = entropy_client
        self._pkg_match = package_match
        self._pkg_id, self._repo_id = package_match
        self._redraw_callback = redraw_callback

    @property
    def name(self):
        """Show user visible name"""
        repo = self._entropy.open_repository(self._repo_id)
        return repo.retrieveName(self._pkg_id)

    def is_installed(self):
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

    def get_markup(self):
        repo = self._entropy.open_repository(self._repo_id)
        name = repo.retrieveName(self._pkg_id)
        if name is None:
            name = "N/A"
        version = repo.retrieveVersion(self._pkg_id)
        if version is None:
            version = "N/A"
        description = repo.retrieveDescription(self._pkg_id)
        if description is None:
            description = _("No description")
        if len(description) > 79:
            description =  description[:80].strip() + "..."
        text = "%s %s\n<small>%s</small>" % (
            GObject.markup_escape_text(name),
            GObject.markup_escape_text(version),
            GObject.markup_escape_text(description))
        return text

    def get_review_stats(self):
        stat = ReviewStats(self)
        stat.ratings_average = ReviewStats.NO_RATING

        repo = self._entropy.open_repository(self._repo_id)
        key_slot = repo.retrieveKeySlot(self._pkg_id)
        if key_slot is None:
            return stat # empty stats
        key, slot = key_slot
        rating = ApplicationMetadata.lazy_get_rating(
            self._entropy, key, self._repo_id,
            callback=self._redraw_callback)
        if rating is None:
            # not ready yet, return empty ratings
            return stat # empty stats
        vote, down = rating
        if vote is not None:
            stat.ratings_average = vote
        if down is not None:
            # otherwise 0 is shown
            stat.ratings_total = down
        return stat

    # get a AppDetails object for this Applications
    def get_details(self):
        """ return a new AppDetails object for this application """
        return AppDetails(self._entropy, self._pkg_match, self)

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

    def __init__(self, entropy_client, package_match, app):
        """
        Create a new AppDetails object.
        """
        self._entropy = entropy_client
        self._pkg_match = package_match
        self._pkg_id, self._repo_id = package_match
        self._app = app

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
        """Return icon name, as it should be searched through fd.o dbs"""
        # FIXME, we have it
        return Icons.MISSING_PKG

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
