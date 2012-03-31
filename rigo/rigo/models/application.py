# -*- coding: utf-8 -*-
"""
Copyright (C) 2009 Canonical
Copyright (C) 2012 Fabio Erculiani

Authors:
  Michael Vogt
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
import time
from collections import deque
from threading import Semaphore, Lock

from gi.repository import GObject

from entropy.const import const_debug_write, const_debug_enabled, \
    const_convert_to_unicode, etpConst
from entropy.exceptions import DependenciesNotRemovable, \
    DependenciesNotFound, DependenciesCollision, EntropyException
from entropy.i18n import _
from entropy.misc import ParallelTask
from entropy.services.client import WebService
from entropy.client.services.interfaces import ClientWebService, \
    DocumentList

import entropy.tools
import entropy.dep

from rigo.enums import Icons
from rigo.utils import build_application_store_url, escape_markup, \
    prepare_markup

class ReviewStats(object):

    NO_RATING = 0

    def __init__(self, app):
        self.app = app
        self.ratings_average = None
        self.downloads_total = -1
        self.rating_spread = [0,0,0,0,0]
        self.dampened_rating = 3.00

    @property
    def downloads_total_markup(self):
        """
        Return a nicer representation of the total downloads amount.
        """
        total = self.downloads_total
        if total < 100:
            text = "< 100"
        elif total < 600:
            text = "500+"
        elif total < 1100:
            text = "1.000+"
        elif total < 2100:
            text = "2.000+"
        elif total < 5100:
            text = "5.000+"
        elif total < 10100:
            text = "10.000+"
        elif total < 20000:
            text = "15.000+"
        elif total < 30000:
            text = "20.000+"
        elif total < 60000:
            text = "50.000+"
        elif total < 110000:
            text = "100.000+"
        elif total < 210000:
            text = "200.000+"
        elif total < 510000:
            text = "500.000+"
        elif total < 1010000:
            text = "1.000.000+"
        elif total < 1510000:
            text = "1.500.000+"
        elif total < 2010000:
            text = "2.000.000+"
        elif total < 5010000:
            text = "5.000.000+"
        elif total < 10010000:
            text = "10.000.000+"
        elif total < 50010000:
            text = "50.000.000+"
        else:
            text = "100.000.000+"
        return escape_markup(text)

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
        self.display_name = escape_markup(display_name)
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
        for th_info in ApplicationMetadata._REGISTERED_THREAD_INFO:
            thread = th_info[0]
            thread.start()

    @staticmethod
    def _rating_thread_body():
        """
        Thread executing package rating remote data retrieval.
        """
        request_list = ["vote", "down"]
        return ApplicationMetadata._generic_thread_body(
            "RatingThread", ApplicationMetadata._RATING_SEM,
            ApplicationMetadata._RATING_DISCARD_SIGNALS,
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
            ApplicationMetadata._ICON_DISCARD_SIGNALS,
            ApplicationMetadata._ICON_THREAD_SLEEP_SECS,
            ApplicationMetadata._ICON_QUEUE,
            ApplicationMetadata._ICON_LOCK,
            ApplicationMetadata._ICON_IN_FLIGHT,
            request_list)

    @staticmethod
    def _generic_thread_body(name, sem, discard_signals, sleep_secs,
                             queue, mutex, in_flight, request_list):
        """
        Thread executing generic (both rating and doc) metadata retrieval.
        """
        cache_miss = WebService.CacheMiss
        ws_exception = WebService.WebServiceException

        def _callback_launch(key, repo_id, cb_ts_list, outcome):
            for (cb, ts) in cb_ts_list:
                with mutex:
                    in_flight.discard((key, repo_id))
                if cb is not None:
                    outcome_values = []
                    for request in request_list:
                        outcome_values.append(
                            outcome[request].get((key, repo_id)))
                    task = ParallelTask(cb, outcome_values, ts)
                    task.name = "%sCb{%s, %s}" % (name, repo_id, key)
                    task.start()

        while True:
            sem.acquire()
            for discard_signal in discard_signals:
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
            visible_cb_map = {}
            for item in local_queue:
                webserv, key, repo_id, cb, still_vis_cb, ts = item

                obj = pkg_key_map.setdefault((key, repo_id), [])
                obj.append((cb, ts))

                obj = repo_map.setdefault(repo_id, set())
                obj.add(key)
                ws_map[repo_id] = webserv

                obj = visible_cb_map.setdefault(key, [])
                obj.append(still_vis_cb)

            request_outcome = {}

            for repo_id, keys in repo_map.items():

                webserv = ws_map[repo_id]
                request_map = {
                    "vote": (webserv.get_votes, {}),
                    "down": (webserv.get_downloads, {}),
                    # for these two, service_cache is broken
                    # and actually useless.
                    "icon": (webserv.get_icons, {}),
                    "comment": (webserv.get_comments, {"latest": True,}),
                }

                for key in keys:

                    # discard signal received ?
                    do_discard = False
                    for discard_signal in discard_signals:
                        if discard_signal.get():
                            do_discard = True
                            break
                    if do_discard:
                        break

                    uncached_requests = []
                    outcome = {}
                    for request in request_list:

                        request_outcome = outcome.setdefault(request, {})
                        request_func, req_kwargs = request_map[request]

                        try:
                            request_outcome[(key, repo_id)] = request_func(
                                [key], cache=True, cached=True,
                                **req_kwargs)[key]
                        except cache_miss:
                            uncached_requests.append(request)

                    # checking if we're still visible
                    is_visible = False
                    for vis_cb in visible_cb_map[key]:
                        if vis_cb is None:
                            is_visible = True
                            break
                        if vis_cb():
                            is_visible = True
                            break
                    if not is_visible:
                        # don't query the remote service
                        uncached_requests = []

                    for request in uncached_requests:

                        request_outcome = outcome[request]
                        request_func, req_kwargs = request_map[request]

                        try:
                            request_outcome[(key, repo_id)] = request_func(
                                [key], cache = True, **req_kwargs)[key]
                        except ws_exception as wse:
                            const_debug_write(
                                __name__,
                                "%s, WebServiceExc: %s" % (name, wse,)
                                )
                            request_outcome[(key, repo_id)] = None

                    cb_ts_list = pkg_key_map[(key, repo_id)]
                    _callback_launch(key, repo_id, cb_ts_list, outcome)

            # don't worry about races
            discarded = False
            for discard_signal in discard_signals:
                if discard_signal.get():
                    const_debug_write(
                        __name__,
                        "%s, discard signal received." % (name,)
                    )
                    discard_signal.set(False)
                    request_outcome.clear()
                    discarded = True
                    break

            if discarded:
                continue


    @staticmethod
    def discard():
        """
        Discard all the queued requests. No longer needed.
        """
        const_debug_write(__name__,
            "ApplicationMetadata.discard() called")
        for th_info in ApplicationMetadata._REGISTERED_THREAD_INFO:
            th, queue, sem, lock, \
                discard_signals, in_flight = th_info
            while True:
                try:
                    queue.popleft()
                    # we could use blocking mode, but no actual need
                    sem.acquire(False)
                except IndexError:
                    break
            with lock:
                in_flight.clear()
            for discard_signal in discard_signals:
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
    def _enqueue_rating(webservice, package_key, repository_id, callback,
                        _still_visible_cb):
        """
        Enqueue the retrieval of the Rating for package key in given repository.
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
                      repository_id, callback,
                      _still_visible_cb, request_time))
        sem.release()

    @staticmethod
    def _enqueue_icon(webservice, package_key, repository_id, callback,
                      _still_visible_cb):
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
                      repository_id, callback,
                      _still_visible_cb, request_time))
        sem.release()

    @staticmethod
    def lazy_get_rating(entropy_ws, package_key, repository_id,
                        callback=None, _still_visible_cb=None):
        """
        Return the Rating (stars) for given package key, if it's available
        in local cache. At the same time, if not available and not already
        enqueued for download, do it, atomically.
        Raise WebService.CacheMiss if not available, the rating otherwise
        (tuple composed by (vote, number_of_downloads)).
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
                        repository_id, callback,
                        _still_visible_cb)
            # let caller handle this
            raise exc

        return vote, down

    @staticmethod
    def download_rating_async(entropy_ws, package_key, repository_id,
                        callback):
        """
        Asynchronously download updated information regarding the
        Rating of given package.
        This request disables local cache usage and directly queries
        the remote Web Service.
        Once data is available, callback will be called passing the returned
        payload as argument.
        For this method, the signature of callback is:
          callback((vote, Number_of_downloads)) [one argument, which is a tuple]
        If the Web Service is not available for repository, None is passed as
        payload of callback.
        Please note that the callback is called from another thread.
        """
        webserv = entropy_ws.get(repository_id)
        if webserv is None:
            task = ParallelTask(callback, None)
            task.name = "DownloadRatingAsync::None"
            task.daemon = True
            task.start()
            return None

        def _getter():
            outcome = None
            try:
                vote = webserv.get_votes(
                    [package_key], cache=False)[package_key]
                down = webserv.get_downloads(
                    [package_key], cache=False)[package_key]
                outcome = (vote, down)
            except WebService.WebServiceException as err:
                const_debug_write(
                    __name__,
                    "Application{%s}.download_rating_async: %s" % (
                        package_key, err,))
            finally:
                # ignore exceptions, if any, and always
                # call callback.
                callback(outcome)

        task = ParallelTask(_getter)
        task.name = "DownloadRatingAsync::Getter"
        task.daemon = True
        task.start()

    @staticmethod
    def lazy_get_icon(entropy_ws, package_key, repository_id,
                        callback=None, _still_visible_cb=None):
        """
        Return a DocumentList of Icons for given package key, if it's available
        in local cache. At the same time, if not available and not already
        enqueued for download, do it, atomically.
        Return None if not available, or DocumentList (see Entropy Services
        API) otherwise. DocumentList contains a list of Document objects,
        and calling Document.local_document() would give you the image path.
        If cache is not available however, WebService.CacheMiss is raised and
        an asynchronous request shall be submitted to the remove web service,
        once data is ready, callback will be called.
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
                        repository_id, _icon_callback,
                        _still_visible_cb)
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

    @staticmethod
    def download_icon_async(entropy_ws, package_key, repository_id,
                            callback):
        """
        Asynchronously download updated information regarding the
        Icon of given package.
        This request disables local cache usage and directly queries
        the remote Web Service.
        Once data is available, callback will be called passing the returned
        payload as argument.
        For this method, the signature of callback is:
          callback(Icon object)
        If the Web Service is not available for repository, None is passed as
        payload of callback.
        Please note that the callback is called from another thread.
        """
        webserv = entropy_ws.get(repository_id)
        if webserv is None:
            task = ParallelTask(callback, None)
            task.name = "DownloadIconAsync::None"
            task.daemon = True
            task.start()
            return None

        def _pick_icon(icons):
            return icons[0]

        def _getter():
            outcome = None
            try:
                icons = webserv.get_icons(
                    [package_key], cache=False)[package_key]

                # pick the first icon as document icon
                icon = _pick_icon(icons)
                # check if we have the file on-disk, otherwise
                # spawn the fetch in parallel.
                icon_path = icon.local_document()
                if not os.path.isfile(icon_path):
                    local_path = ApplicationMetadata._download_document(
                        webserv, icon)
                    if local_path:
                        outcome = icon
            except WebService.WebServiceException as err:
                const_debug_write(
                    __name__,
                    "Application{%s}.download_icon_async: %s" % (
                        package_key, err,))
            finally:
                # ignore exceptions, if any, and always
                # call callback.
                callback(outcome)

        task = ParallelTask(_getter)
        task.name = "DownloadIconAsync::Getter"
        task.daemon = True
        task.start()

    @staticmethod
    def download_comments_async(entropy_ws, package_key, repository_id,
                                offset, callback):
        """
        Asynchronously download updated information regarding the
        comments of the given application.
        This request disables local cache usage and directly queries
        the remote Web Service.
        Once data is available, callback will be called passing the returned
        payload as argument.
        For this method, the signature of callback is:
          callback(DocumentList)
        If the Web Service is not available for repository, None is passed as
        payload of callback.
        Please note that the callback is called from another thread.
        """
        webserv = entropy_ws.get(repository_id)
        if webserv is None:
            task = ParallelTask(callback, None)
            task.name = "DownloadCommentsAsync::None"
            task.daemon = True
            task.start()
            return None

        def _getter():
            outcome = None
            try:
                outcome = webserv.get_comments(
                    [package_key], cache=False,
                    latest=True, offset=offset)[package_key]
            except WebService.WebServiceException as err:
                const_debug_write(
                    __name__,
                    "Application{%s}.download_comments_async: %s" % (
                        package_key, err,))
            finally:
                # ignore exceptions, if any, and always
                # call callback.
                callback(outcome)

        task = ParallelTask(_getter)
        task.name = "DownloadCommentsAsync::Getter"
        task.daemon = True
        task.start()

    @staticmethod
    def download_images_async(entropy_ws, package_key, repository_id,
                                offset, callback, ignore_icons=True):
        """
        Asynchronously download updated information regarding the images
        of the given application.
        This request disables local cache usage and directly queries
        the remote Web Service.
        Once data is available, callback will be called passing the returned
        payload as argument.
        For this method, the signature of callback is:
          callback(DocumentList)
        If the Web Service is not available for repository, None is passed as
        payload of callback.
        Please note that the callback is called from another thread.
        """
        webserv = entropy_ws.get(repository_id)
        if webserv is None:
            task = ParallelTask(callback, None)
            task.name = "DownloadImagesAsync::None"
            task.daemon = True
            task.start()
            return None

        def _getter():
            outcome = None
            try:
                images = webserv.get_images(
                    [package_key], cache=False,
                    latest=True, offset=offset)[package_key]

                fetched_images = []
                for image in images:
                    if image.is_icon() and ignore_icons:
                        continue
                    # check if we have the file on-disk, otherwise
                    # spawn the fetch in parallel.
                    image_path = image.local_document()
                    if not os.path.isfile(image_path):
                        local_path = ApplicationMetadata._download_document(
                            webserv, image)
                        if local_path:
                            fetched_images.append(image)
                    else:
                        fetched_images.append(image)

                # final DocumentList may contain less elements
                # than those advertised by total().
                _outcome = DocumentList(
                    images.package_name(),
                    images.total(),
                    images.offset())
                _outcome.extend(fetched_images)
                outcome = _outcome

            except WebService.WebServiceException as err:
                const_debug_write(
                    __name__,
                    "Application{%s}.download_images_async: %s" % (
                        package_key, err,))
            finally:
                # ignore exceptions, if any, and always
                # call callback.
                callback(outcome)

        task = ParallelTask(_getter)
        task.name = "DownloadImagesAsync::Getter"
        task.daemon = True
        task.start()


    class SignalBoolean(object):

        def __init__(self, val):
            self.__val = val

        def set(self, val):
            self.__val = val

        def get(self):
            return self.__val

    _REGISTERED_THREAD_INFO = []

    _RATING_WORKERS = 3
    _ICON_WORKERS = 3

    _ICON_DISCARD_SIGNALS = []
    _RATING_DISCARD_SIGNALS = []

    # Application Rating logic
    _RATING_QUEUE = deque()
    def _rating_thread_body_wrapper():
        return ApplicationMetadata._rating_thread_body()
    _RATING_THREAD_SLEEP_SECS = 0.5
    _RATING_SEM = Semaphore(0)
    _RATING_LOCK = Lock()
    _RATING_IN_FLIGHT = set()

    for i in range(_RATING_WORKERS):
        th = ParallelTask(_rating_thread_body_wrapper)
        th.daemon = True
        th.name = "RatingThread-%s" % (i,)
        discard_signal = SignalBoolean(False)
        _REGISTERED_THREAD_INFO.append(
            (th, _RATING_QUEUE,
             _RATING_SEM, _RATING_LOCK,
             _RATING_DISCARD_SIGNALS,
             _RATING_IN_FLIGHT))
        _RATING_DISCARD_SIGNALS.append(discard_signal)

    # Application Icons logic
    _ICON_QUEUE = deque()
    def _icon_thread_body_wrapper():
        return ApplicationMetadata._icon_thread_body()
    _ICON_THREAD_SLEEP_SECS = 0.15
    _ICON_SEM = Semaphore(0)
    _ICON_LOCK = Lock()
    _ICON_IN_FLIGHT = set()

    for i in range(_ICON_WORKERS):
        th = ParallelTask(_icon_thread_body_wrapper)
        th.daemon = True
        th.name = "IconThread-%s" % (i,)
        discard_signal = SignalBoolean(False)
        _REGISTERED_THREAD_INFO.append(
            (th, _ICON_QUEUE,
             _ICON_SEM, _ICON_LOCK,
             _ICON_DISCARD_SIGNALS,
             _ICON_IN_FLIGHT))
        _ICON_DISCARD_SIGNALS.append(discard_signal)


# this is a very lean class as its used in the main listview
# and there are a lot of application objects in memory
class Application(object):
    """
    The central software item abstraction. it contains a
    pkgname that is always available and a optional appname
    for packages with multiple applications
    There is also a __cmp__ method and a name property
    """

    class AcceptLicenseError(EntropyException):

        """
        Exception raised when Application can be installed
        but licenses have to be accepted. The get() method
        returns a mapping composed by license id as key and
        list of Application objects as value.
        """

        def __init__(self, license_map):
            self._licenses = license_map

        def get(self):
            """
            Return the Licenses to accept in mapping form:
            license id as key, list of Application objects as
            value.
            """
            return self._licenses

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
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            name = repo.retrieveName(self._pkg_id)
            if name is None:
                return _("N/A")
            name = " ".join([x.capitalize() for x in \
                                 name.replace("-"," ").split()])
            return escape_markup(name)
        finally:
            self._entropy.rwsem().reader_release()

    def is_installed(self):
        """
        Return if Application is currently installed.
        """
        app = self.get_installed()
        return app is not None

    def is_installed_app(self):
        """
        Return whether this Application object describes an
        Installed one.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            return self._is_installed_app()
        finally:
            self._entropy.rwsem().reader_release()

    def _is_installed_app(self):
        """
        Return whether this Application object describes an
        Installed one.
        """
        repo = self._entropy.open_repository(self._repo_id)
        inst_repo = self._entropy.installed_repository()
        return repo is inst_repo

    def _get_installed(self):
        """
        Application.get_installed() method body.
        """
        inst_repo = self._entropy.installed_repository()
        repo = self._entropy.open_repository(self._repo_id)

        key_slot_tag = repo.retrieveKeySlotTag(self._pkg_id)
        if key_slot_tag is None:
            return None

        key, slot, tag = key_slot_tag
        matches = inst_repo.searchKeySlotTag(key, slot, tag)
        # in the installed packages repository, matches
        # must be of length < 2.
        if len(matches) > 1:
            raise AttributeError(
                "searchKeySlot for %s returned: %s" % (
                    (key, slot), matches,))
        if not matches:
            # not installed
            return None

        package_id = list(matches)[0]
        if inst_repo is repo:
            # return ourselves if we're already representing
            # an installed App (is_removable() expects that)
            return self
        return Application(self._entropy, self._entropy_ws,
                           (package_id, inst_repo.repository_id()),
                           redraw_callback=self._redraw_callback)

    def _source_repository_id(self, repo):
        """
        Return the actual repository name (if possible) if
        Application is coming from the Installed Packages Repository.
        """
        inst_repo = self._entropy.installed_repository()
        repository_id = repo.repository_id()
        if repo is inst_repo:
            # get source repository id, because installed repo
            # id won't work
            _repository_id = repo.getInstalledPackageRepository(
                self._pkg_id)
            if _repository_id is not None:
                repository_id = _repository_id
        return repository_id

    def get_installed(self):
        """
        Return the Application object of the installed
        application (rather than the available one), or
        None if not installed.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            return self._get_installed()
        finally:
            self._entropy.rwsem().reader_release()

    def is_updatable(self):
        """
        Return if Application can be updated.
        With "updated" we also mean "downgraded".
        """
        self._entropy.rwsem().reader_acquire()
        try:
            inst_repo = self._entropy.installed_repository()
            repo = self._entropy.open_repository(self._repo_id)
            if repo is inst_repo:
                return False
            pkgcmp = self._entropy.get_package_action(
                (self._pkg_id, self._repo_id))
            # 0 = reinstall
            # 1 = new package
            # 2 = update
            # else = downgrade
            if pkgcmp == 2:
                return True
            elif pkgcmp == 0:
                return False
            elif pkgcmp == 1:
                return False
            else:
                return True
        finally:
            self._entropy.rwsem().reader_release()

    def is_removable(self):
        """
        Return if Application can be removed or it's part of
        the Base System.
        """
        installed = self.get_installed()
        if installed is not self:
            return installed.is_removable()

        self._entropy.rwsem().reader_acquire()
        try:
            removable = self._entropy.validate_package_removal(
                self._pkg_id)
            if removable:
                return True

            try:
                self._entropy.get_reverse_queue(
                    [(self._pkg_id, self._repo_id)])
                return True
            except DependenciesNotRemovable:
                return False
        finally:
            self._entropy.rwsem().reader_release()

    def _get_install_queue(self):
        """
        Return Application install and removal queues.
        """
        inst_repo = self._entropy.installed_repository()
        repo = self._entropy.open_repository(self._repo_id)
        if repo is inst_repo:
            return None

        pkg_match = self.get_details().pkg
        masked = self._entropy.is_package_masked(pkg_match)
        if masked:
            return None

        try:
            install_queue, removal_queue = \
                self._entropy.get_install_queue(
                    [pkg_match], False, False)
        except DependenciesNotFound:
            raise
        except DependenciesCollision:
            raise

        return install_queue, removal_queue

    def get_install_conflicts(self):
        """
        Return a list of Application objects belonging to
        Apps that would need to be removed of this Application
        is installed.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            apps = []
            queues = self._get_install_queue()
            if queues is None:
                return apps
            install, removal = queues
            del install

            inst_repo = self._entropy.installed_repository()
            inst_repo_id = inst_repo.repository_id()
            for inst_pkg_id in removal:
                app = Application(
                    self._entropy, self._entropy_ws,
                    (inst_pkg_id, inst_repo_id))
                apps.append(app)
            return apps
        finally:
            self._entropy.rwsem().reader_release()

    def is_installable(self):
        """
        Return if Application can be installed or it's masked
        or one of its dependencies are.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            queues = self._get_install_queue()
            if queues is None:
                return False
            install, removal = queues

            # check licenses
            licenses = self._entropy.get_licenses_to_accept(install)
            if licenses:
                license_map = {}
                for lic_id, pkg_matches in licenses.items():
                    obj = license_map.setdefault(lic_id, [])
                    for pkg_match in pkg_matches:
                        app = Application(
                            self._entropy, self._entropy_ws,
                            pkg_match)
                        obj.append(app)
                raise Application.AcceptLicenseError(license_map)

        except DependenciesNotFound:
            return False
        except DependenciesCollision:
            return False

        finally:
            self._entropy.rwsem().reader_release()

        return True

    def is_available(self):
        """
        Return if Application is actually available in repos,
        for cache reasons?
        The actual semantics of this method in softwarecenter
        seems quite ambiguous to me.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return repo.isPackageIdAvailable(self._pkg_id)
        finally:
            self._entropy.rwsem().reader_release()

    def get_markup(self):
        """
        Get Application markup text.
        """
        name = self.name
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            version = repo.retrieveVersion(self._pkg_id)
            if version is None:
                version = _("N/A")
            tag = repo.retrieveTag(self._pkg_id)
            if not tag:
                tag = ""
            else:
                tag = "#" + tag
            description = repo.retrieveDescription(self._pkg_id)
            if description is None:
                description = _("No description")
            if len(description) > 79:
                description =  description[:80].strip() + "..."
            text = "<b>%s</b> %s%s\n<small><i>%s</i></small>" % (
                name,
                escape_markup(version),
                escape_markup(tag),
                escape_markup(description))
            return text
        finally:
            self._entropy.rwsem().reader_release()

    def search(self, keyword):
        """
        Match keyword against Application name. Return True if
        the same contains keyword.
        """
        name = self.name
        if keyword in name:
            return True
        return keyword.lower() in name.lower()

    def get_extended_markup(self):
        """
        Get Application markup text (extended version).
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            inst_repo = self._entropy.installed_repository()
            strict = repo.getStrictData(self._pkg_id)
            if strict is None:
                return _("N/A")
            key, slot, version, tag, revision, atom = strict

            name = key.split("/", 1)[-1]
            # make it cute
            name = " ".join([x.capitalize() for x in \
                                 name.replace("-"," ").split()])
            name = escape_markup(name)
            website = repo.retrieveHomepage(self._pkg_id)
            if website:
                name = "<a href=\"%s\">%s</a>" % (
                    escape_markup(website),
                    name,)

            if not tag:
                tag = ""
            else:
                tag = "#" + tag

            revision_txt = "~%d" % (revision,)

            description = repo.retrieveDescription(self._pkg_id)
            if description is None:
                description = _("No description")
            if len(description) > 79:
                description =  description[:80].strip() + "..."

            cdate = repo.retrieveCreationDate(self._pkg_id)
            if cdate:
                date = time.strftime("%B %d, %Y",
                    time.gmtime(float(cdate))).capitalize()
            else:
                date = _("N/A")

            from_str = self._repo_id
            installed_str = ""
            if repo is inst_repo:
                from_str = _("Installed")
            else:
                inst_app = self._get_installed()
                if inst_app is not None:
                    ver = inst_app.get_details().version
                    installed_str = "\n" + prepare_markup(
                        _("<b>%s</b> is installed") % (ver,))

            repo_from = "%s <b>%s</b>" % (escape_markup(_("from")),
                                          escape_markup(from_str),)

            text = "<b>%s</b> %s%s%s\n<small><i>%s</i>\n%s, %s%s</small>" % (
                    name,
                    escape_markup(version),
                    escape_markup(tag),
                    escape_markup(revision_txt),
                    escape_markup(description),
                    escape_markup(date),
                    repo_from,
                    installed_str,
                    )
            return text
        finally:
            self._entropy.rwsem().reader_release()

    def get_info_markup(self):
        """
        Get Application info markup text.
        """
        app_store_url = build_application_store_url(self, "")

        self._entropy.rwsem().reader_acquire()
        try:
            lic_url = "%s/license/" % (etpConst['packages_website_url'],)
            repo = self._entropy.open_repository(self._repo_id)

            licenses = repo.retrieveLicense(self._pkg_id)
            if licenses:
                licenses_txt = "<b>%s</b>: " % (escape_markup(_("License")),)
                licenses_txt += ", ".join(sorted([
                            "<a href=\"%s%s\">%s</a>" % (lic_url, x, x) \
                                for x in licenses.split()]))
            else:
                licenses_txt = ""

            required_space = repo.retrieveOnDiskSize(self._pkg_id)
            if required_space is None:
                required_space = 0
            required_space_txt = "<b>%s</b>: %s" % (
                escape_markup(_("Required space")),
                escape_markup(entropy.tools.bytes_into_human(required_space)),)

            down_size = repo.retrieveSize(self._pkg_id)
            if down_size is None:
                down_size = 0
            down_size_txt = "<b>%s</b>: %s" % (
                escape_markup(_("Download size")),
                escape_markup(entropy.tools.bytes_into_human(down_size)),)

            digest = repo.retrieveDigest(self._pkg_id)
            if digest is None:
                digest = _("N/A")
            digest_txt = "<b>%s</b>: %s" % (
                escape_markup(_("Checksum")),
                escape_markup(digest))

            uses = repo.retrieveUseflags(self._pkg_id)
            uses = sorted(uses)
            use_list = []
            use_url = "%s/useflag/" % (etpConst['packages_website_url'],)
            for use in uses:
                use_m = escape_markup(use)
                txt = "<a href=\"%s%s\">%s</a>" % (use_url, use_m, use_m)
                use_list.append(txt)
            use_txt = "<b>%s</b>: " % (escape_markup(_("USE flags")),)
            if use_list:
                use_txt += " ".join(use_list)
            else:
                use_txt += escape_markup(_("No use flags"))

            rdepend_id = etpConst['dependency_type_ids']['rdepend_id']
            pdepend_id = etpConst['dependency_type_ids']['pdepend_id']
            bdepend_id = etpConst['dependency_type_ids']['bdepend_id']
            mdepend_id = etpConst['dependency_type_ids']['mdepend_id']

            deps = repo.retrieveDependencies(
                self._pkg_id, extended=True,
                resolve_conditional_deps=False)
            runtime_deps = [x for x, y in deps if y == rdepend_id]
            build_deps = [x for x, y in deps if y == bdepend_id]
            post_deps = [x for x, y in deps if y == pdepend_id]
            manual_deps = [x for x, y in deps if y == mdepend_id]

            depsorter = lambda x: entropy.dep.dep_getcpv(x)

            dep_couples = [
                (runtime_deps, _("Runtime dependencies")),
                (build_deps, _("Build dependencies")),
                (post_deps, _("Post dependencies")),
                (manual_deps, _("Staff dependencies"))
            ]
            dep_txts = []
            for dep_list, dep_title in dep_couples:
                if not dep_list:
                    continue
                dep_txt = "<b>%s</b>" % (escape_markup(dep_title),)
                for dep in sorted(dep_list, key=depsorter):
                    dep_mk = escape_markup(dep)
                    dep_txt += "\n      <a href=\"app://%s\">%s</a>" % (
                        dep_mk, dep_mk,)
                dep_txts.append(dep_txt)

            deps_txt = "\n".join(dep_txts)
            if deps_txt:
                deps_txt += "\n\n"

            if self._is_installed_app():
                more_txt = ""
            else:
                more_txt = "<a href=\"%s\"><b>%s</b></a>" % (
                    app_store_url,
                    escape_markup(_("Click here for more details")),)

            text = "<small>%s\n%s\n%s\n%s\n%s\n%s%s</small>" % (
                down_size_txt,
                required_space_txt,
                licenses_txt,
                digest_txt,
                use_txt,
                deps_txt,
                more_txt,
                )
            return text
        finally:
            self._entropy.rwsem().reader_release()

    def get_review_stats(self, _still_visible_cb=None):
        """
        Return ReviewStats object containing user review
        information about this Application, like
        votes and number of downloads.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            stat = ReviewStats(self)
            stat.ratings_average = ReviewStats.NO_RATING

            repo = self._entropy.open_repository(self._repo_id)
            key_slot = repo.retrieveKeySlot(self._pkg_id)
            if key_slot is None:
                return stat # empty stats
            key, slot = key_slot
            try:
                rating = ApplicationMetadata.lazy_get_rating(
                    self._entropy_ws, key,
                    self._source_repository_id(repo),
                    callback=self._redraw_callback,
                    _still_visible_cb=_still_visible_cb)
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
        finally:
            self._entropy.rwsem().reader_release()

    def get_icon(self, _still_visible_cb=None):
        """
        Return Application Icon image Entropy Document object.
        In case of missing icon, None is returned.
        The actual outcome of this property is a tuple, composed
        by the Document object (or None) and cache hit information
        (True if got from local cache, False if not in local cache)
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            key_slot = repo.retrieveKeySlot(self._pkg_id)
            if key_slot is None:
                return None, False

            key, slot = key_slot
            cache_hit = True
            try:
                icon = ApplicationMetadata.lazy_get_icon(
                    self._entropy_ws, key,
                    self._source_repository_id(repo),
                    callback=self._redraw_callback,
                    _still_visible_cb=_still_visible_cb)
            except WebService.CacheMiss:
                cache_hit = False
                icon = None

            if const_debug_enabled():
                const_debug_write(__name__,
                    "Application{%s}.get_icon: icon: %s, cache hit: %s" % (
                        self._pkg_match,
                        icon, cache_hit))

            return icon, cache_hit
        finally:
            self._entropy.rwsem().reader_release()

    def download_comments(self, callback, offset=0):
        """
        Return Application Comments Entropy Document object.
        In case of missing comments (locally), None is returned.
        The actual outcome of this method is a DocumentList object.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            key_slot = repo.retrieveKeySlot(self._pkg_id)
            if key_slot is None:
                task = ParallelTask(callback, None)
                task.name = "DownloadCommentsNoneCallback"
                task.daemon = True
                task.start()
                return

            key, slot = key_slot
            ApplicationMetadata.download_comments_async(
                self._entropy_ws, key, self._source_repository_id(repo),
                offset, callback)

            if const_debug_enabled():
                const_debug_write(__name__,
                    "Application{%s}.download_comments called" % (
                        self._pkg_match,))
        finally:
            self._entropy.rwsem().reader_release()

    def download_images(self, callback, offset=0):
        """
        Return Application Images Entropy Document object.
        In case of missing comments (locally), None is returned.
        The actual outcome of this method is a DocumentList object.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            key_slot = repo.retrieveKeySlot(self._pkg_id)
            if key_slot is None:
                task = ParallelTask(callback, None)
                task.name = "DownloadImagesNoneCallback"
                task.daemon = True
                task.start()
                return

            key, slot = key_slot
            ApplicationMetadata.download_images_async(
                self._entropy_ws, key, self._source_repository_id(repo),
                offset, callback)

            if const_debug_enabled():
                const_debug_write(__name__,
                    "Application{%s}.download_images called" % (
                        self._pkg_match,))
        finally:
            self._entropy.rwsem().reader_release()

    def is_webservice_available(self):
        """
        Return whether the Entropy Web Service is available
        for this Application.
        """
        webserv = self._entropy_ws.get(self._repo_id)
        if webserv:
            return True
        return False

    def get_webservice_username(self):
        """
        Return the currently logged Entropy Web Services
        username, or None, if any.
        """
        webserv = self._entropy_ws.get(self._repo_id)
        if webserv is None:
            return None
        return webserv.get_credentials()

    # get a AppDetails object for this Applications
    def get_details(self):
        """
        Return a new AppDetails object for this application
        """
        return AppDetails(self._entropy, self._entropy_ws,
                          self._pkg_match, self,
                          redraw_callback=self._redraw_callback)

    def __str__(self):
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            atom = repo.retrieveAtom(self._pkg_id)
            return "(%s: %s)" % (self._pkg_match, atom)
        finally:
            self._entropy.rwsem().reader_release()

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
        """
        Return Application Channel (repository identifier).
        """
        return self._repo_id

    @property
    def sourcechannel(self):
        """
        Return Application Source Channel (if this is an Installed
        Application, the Channel of the original repository shall
        be returned).
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return self._app._source_repository_id(repo)
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def description(self):
        """
        Return Application short description.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return repo.retrieveDescription(self._pkg_id)
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def error(self):
        return _("Application not found")

    @property
    def installation_date(self):
        """
        Return human readable representation of the installation
        date, if installed, or None otherwise.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            inst_repo = self._entropy.installed_repository()
            if repo is inst_repo:
                return entropy.tools.convert_unix_time_to_human_time(
                    float(repo.retrieveCreationDate(self._pkg_id)))
            keyslot = repo.retrieveKeySlotAggregated(self._pkg_id)
            pkg_id, rc = inst_repo.atomMatch(keyslot)
            if pkg_id != -1:
                return entropy.tools.convert_unix_time_to_human_time(
                    float(inst_repo.retrieveCreationDate(pkg_id)))
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def date(self):
        """
        Return human readable representation of the date the
        Application has been last updated.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return entropy.tools.convert_unix_time_to_human_time(
                float(repo.retrieveCreationDate(self._pkg_id)))
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def licenses(self):
        """
        Return list of license identifiers for Application.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            licenses = repo.retrieveLicense(self._pkg_id)
            if not licenses:
                return []
            return licenses.split()
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def downsize(self):
        """
        Return the download size in bytes.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return repo.retrieveSize(self._pkg_id)
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def name(self):
        """
        Return the name of the application, this will always
        return Application.name. Most UI will want to use
        the property display_name instead
        """
        return self._app.name

    @property
    def display_name(self):
        """
        Return the application name as it should be displayed in the UI
        If the appname is defined, just return it, else return
        the summary (per the spec)
        """
        return self.name

    @property
    def pkg(self):
        """
        Return unique identifier belonging to this Application.
        """
        return self._pkg_match

    @property
    def pkgname(self):
        """
        Return unmangled package name belonging to this Application.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return repo.retrieveName(self._pkg_id)
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def fullname(self):
        """
        Return unmangled package name belonging to this Application.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return repo.retrieveAtom(self._pkg_id)
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def pkgkey(self):
        """
        Return unmangled package key name belonging to this Application.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            key, slot = repo.retrieveKeySlot(self._pkg_id)
            return key
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def signing_key_id(self):
        """
        Return GPG key identifier used to sign the Application.
        """
        return self._repo_id

    @property
    def version(self):
        """
        Return Application version (without revision and tag).
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            ver = repo.retrieveVersion(self._pkg_id)
            tag = repo.retrieveTag(self._pkg_id)
            if tag:
                ver += etpConst['entropytagprefix'] + tag
            return ver
        finally:
            self._entropy.rwsem().reader_release()

    @property
    def website(self):
        """
        Return Application official Website URL or None.
        """
        self._entropy.rwsem().reader_acquire()
        try:
            repo = self._entropy.open_repository(self._repo_id)
            return repo.retrieveHomepage(self._pkg_id)
        finally:
            self._entropy.rwsem().reader_release()