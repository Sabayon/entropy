import os
import tempfile
from threading import Lock

from entropy.services.client import WebService

class EntropyWebService(object):

    def __init__(self, entropy_client, tx_callback=None):
        # Install custom CACHE_DIR pointing it to our
        # home directory. This way we don't need to mess
        # with privileges, resulting in documents not
        # downloadable.
        home_dir = os.getenv("HOME")
        if home_dir is None:
            home_dir = tempfile.mkdtemp(prefix="EntropyWebService")
        ws_cache_dir = os.path.join(home_dir, ".entropy", "ws_cache")
        WebService.CACHE_DIR = ws_cache_dir
        self._entropy = entropy_client
        self._webserv_map = {}
        self._tx_callback = tx_callback
        self._mutex = Lock()

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
            except WebService.UnsupportedService as err:
                webserv = None

        if webserv is None:
            self._webserv_map[repository_id] = -1
            # not available
            return None

        try:
            available = webserv.service_available()
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
