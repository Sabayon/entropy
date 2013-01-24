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
import tempfile
from threading import Lock

from rigo.paths import CONF_DIR

from entropy.misc import ReadersWritersSemaphore
from entropy.services.client import WebService
from entropy.client.interfaces import Client

class EntropyWebService(object):

    # This is sufficient for Votes and Downloads.
    # The other metadata follow another cache validation
    # policy anyway.
    CACHE_AGING_DAYS = 14

    def __init__(self, entropy_client, tx_callback=None):
        # Install custom CACHE_DIR pointing it to our
        # home directory. This way we don't need to mess
        # with privileges, resulting in documents not
        # downloadable.
        ws_cache_dir = os.path.join(CONF_DIR, "ws_cache")
        WebService.CACHE_DIR = ws_cache_dir
        self._entropy = entropy_client
        self._webserv_map = {}
        self._tx_callback = tx_callback
        self._mutex = Lock()

    def preload(self):
        """
        Preload the Web Services objects in memory.
        """
        for repository_id in self._entropy.repositories():
            self.get(repository_id)

    def get(self, repository_id):
        """
        Get Entropy Web Services service object (ClientWebService).

        @param repository_id: repository identifier
        @type repository_id: string
        @return: the ClientWebService instance
        @rtype: entropy.client.services.interfaces.ClientWebService
        @raise WebService.UnsupportedService: if service is unsupported by
        repository
        """
        webserv = self._webserv_map.get(repository_id)
        if webserv == -1:
            # not available
            return None
        if webserv is not None:
            return webserv

        with self._mutex:
            webserv = self._webserv_map.get(repository_id)
            if webserv == -1:
                # not available
                return None
            if webserv is not None:
                return webserv

            try:
                webserv = self._get(self._entropy, repository_id)
                webserv.enable_cache_aging(self.CACHE_AGING_DAYS)
            except WebService.UnsupportedService as err:
                webserv = None

        if webserv is None:
            self._webserv_map[repository_id] = -1
            # not available
            return None

        try:
            # we cannot rely on local cache because the
            # network availability may have changed.
            # even tho, we should check this every time
            # we're asked to return from get().
            # Moreover, using local cache without Internet
            # connectivity would result in a crazy amount
            # of requests floating around the process.
            available = webserv.service_available(cache=False)
        except WebService.WebServiceException:
            available = False

        if not available:
            with self._mutex:
                if repository_id not in self._webserv_map:
                    self._webserv_map[repository_id] = -1
            return

        with self._mutex:
            if repository_id not in self._webserv_map:
                self._webserv_map[repository_id] = webserv
        return webserv

    def _get(self, entropy_client, repository_id):
        """
        Get Entropy Web Services service object (ClientWebService).

        @param entropy_client: Entropy Client interface
        @type entropy_client: entropy.client.interfaces.Client
        @param repository_id: repository identifier
        @type repository_id: string
        @return: the ClientWebService instance
        @rtype: entropy.client.services.interfaces.ClientWebService
        @raise WebService.UnsupportedService: if service is unsupported by
        repository
        """
        factory = entropy_client.WebServices()
        webserv = factory.new(repository_id)
        if self._tx_callback is not None:
            webserv._set_transfer_callback(self._tx_callback)
        return webserv

class EntropyClient(Client):
    """
    Entropy Client Interface object.
    """

    _RWSEM = ReadersWritersSemaphore()

    def rwsem(self):
        """
        Return a Readers/Writers semaphore object that
        arbitrates concurrent access to shared, non-atomic
        resources such as cached EntropyRepository objects.
        """
        return EntropyClient._RWSEM
Client.__singleton_class__ = EntropyClient
