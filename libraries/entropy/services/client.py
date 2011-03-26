# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Base Repository Web Services client interface}.

"""
__all__ = ["WebServiceFactory", "WebService"]

import sys
import os
import errno
import json
import tempfile
import threading
import hashlib
import urllib
import socket
if sys.hexversion >= 0x3000000:
    import http.client as httplib
    from io import StringIO
else:
    import httplib
    from cStringIO import StringIO

import entropy.dump
from entropy.core import Singleton
from entropy.cache import EntropyCacher
from entropy.const import const_debug_write, const_setup_file, etpConst, \
    const_convert_to_rawstring, const_isunicode
from entropy.exceptions import EntropyException
import entropy.tools
import entropy.dep

class WebServiceFactory(object):
    """
    Base Entropy Repository Web Services Factory. Generates
    WebService objects that can be used to communicate with the established
    web service.
    This is a base class and subclasses should be preferred (example:
    entropy.client.services.interfaces.ClientWebServiceFactory)
    """
    class InvalidWebServiceFactory(EntropyException):
        """
        Raised when an invalid WebService based class is passed.
        """

    def __init__(self, web_service_class, entropy_client):
        """
        WebServiceFactory constructor.

        @param entropy_client: Entropy Client interface
        @type entropy_client: entropy.client.interfaces.client.Client
        """
        object.__init__(self)
        if not issubclass(web_service_class, WebService):
            raise InvalidWebServiceFactory("invalid web_service_class")
        self._entropy = entropy_client
        self._service_class = web_service_class

    def new(self, repository_id):
        """
        Return a new WebService object for given repository identifier.

        @param repository_id: repository identifier
        @rtype repository_id: string
        @raise WebService.UnsupportedService: if web service is
            explicitly unsupported by repository
        """
        return self._service_class(self._entropy, repository_id)


class WebService(object):
    """
    This is the Entropy Repository Web Services that proxies requests over
    an Web Services answering to HTTP POST requests
    (either over HTTP or over HTTPS) in the following form:

    Given that repositories must ship with a file (in their repository
    meta file "packages.db.meta", coming from the server-side repository
    directory) called "packages.db.webservices"
    (etpConst['etpdatabasewebservicesfile']) containing the HTTP POST base
    URL (example: http://packages.sabayon.org/api).
    The POST url is composed as follows:
        <base_url>/<method name>
    Function arguments are then appended in JSON format, so that float, int,
    strings and lists are correctly represented.
    So, for example, if WebService exposes a method with the following
    signature (with the base URL in example above):

        float get_vote(string package_name)

    The URL referenced will be:

        http://packages.sabayon.org/api/get_vote

    And the JSON dictionary will contain a key called "package_name" with
    package_name value.
    For methods requiring authentication, the JSON object will contain
    "username" and "password" fields (clear text, so make sure to use HTTPS).

    The Response depends on each specific method and it is given in JSON format
    too, that is afterwards interpreted by the caller function, that will
    always return the expected data format (see respective API documentation).
    For more information about how to implement the Web Service, please see
    the packages.git Sabayon repository, which contains a Pylons MVC web app.
    In general, every JSON response must provide a 'code' field, representing
    an HTTP-response alike return code (200 is ok, 500 is server error, 400 is
    bad request, etc) and a 'message' field, containing the error message (if
    no error, 'message' is usually empty). The RPC result is put inside the
    'r' field.

    This is a base class, and you should really implement a subclass providing
    your own API methods, and use _method_getter().
    """

    # Supported communcation protocols
    SUPPORTED_URL_SCHEMAS = ("http", "https")

    # package icon metadata identifier
    PKG_ICON_IDENTIFIER = "__icon__"

    # Currently supported Web Service API level
    # an API level defines a set of available remote calls and their data
    # structure
    SUPPORTED_API_LEVEL = 1

    # Default common Web Service responses
    WEB_SERVICE_RESPONSE_CODE_OK = 200
    WEB_SERVICE_INVALID_CREDENTIALS_CODE = 450


    class WebServiceException(EntropyException):
        """
        Base WebService exception class.
        """

    class UnsupportedService(WebServiceException):
        """
        Raised when Repository doesn't seem to support any Web Service
        feature.
        """

    class UnsupportedParameters(WebServiceException):
        """
        Raised when input parameters cannot be converted to JSON.
        Probably due to invalid input data.
        """

    class RequestError(WebServiceException):
        """
        If the request cannot be satisfied by the remote web service.
        """

    class AuthenticationRequired(WebServiceException):
        """
        When a method requiring valid user credentials is called without
        being logged in.
        """

    class AuthenticationFailed(WebServiceException):
        """
        When credentials are stored locally but don't seem to work against
        the Web Service.
        """

    class MethodNotAvailable(WebServiceException):
        """
        When calling a remote method that is not available.
        """

    class MalformedResponse(WebServiceException):
        """
        If JSON response cannot be converted back to dict.
        """

    class UnsupportedAPILevel(WebServiceException):
        """
        If this client and the Web Service expose a different API level.
        """

    class MethodResponseError(WebServiceException):
        """
        If the request has been accepted, but its computation stopped for
        some reason. The encapsulated data contains the error code.
        """

    def __init__(self, entropy_client, repository_id):
        """
        WebService constructor.

        @param entropy_client: Entropy Client interface
        @type entropy_client: entropy.client.interfaces.client.Client
        @param repository_id: repository identifier
        @rtype repository_id: string
        """
        self._cache_dir_lock = threading.RLock()
        self._transfer_callback = None
        self._entropy = entropy_client
        self._repository_id = repository_id
        self.__auth_storage = None
        self.__settings = None
        self.__cacher = None
        self._default_timeout_secs = 5.0
        self.__credentials_validated = False

        # check availability
        _repository_data = self._settings['repositories']['available'].get(
            self._repository_id)
        if _repository_data is None:
            raise WebService.UnsupportedService("unsupported")
        self._repository_data = _repository_data
        web_services_conf = self._repository_data['webservices_config']

        # mainly for debugging purposes, hidden and undocumented
        override_request_url = os.getenv("ETP_OVERRIDE_REQUEST_URL")
        if override_request_url is not None:
            _remote_url = override_request_url
        else:
            try:
                with open(web_services_conf, "r") as web_f:
                    # currently, in this file there is only the remote base URL
                    _remote_url = web_f.readline().strip()
            except (OSError, IOError) as err:
                const_debug_write(__name__, "WebService.__init__ error: %s" % (
                    err,))
                raise WebService.UnsupportedService(err)

        url_obj = entropy.tools.spliturl(_remote_url)
        if url_obj.scheme not in WebService.SUPPORTED_URL_SCHEMAS:
            raise WebService.UnsupportedService("unsupported url")
        self._request_url = _remote_url
        self._request_protocol = url_obj.scheme
        self._request_host = url_obj.netloc
        self._request_path = url_obj.path

        const_debug_write(__name__, "WebService loaded, url: %s" % (
            self._request_url,))

    def _set_transfer_callback(self, callback):
        """
        Set a transfer progress callback function.

        @param transfer_callback: this callback function can be used to
            show a progress status to user, if passed, it must be a function
            accepting 3 input parameters: (int transfered, int total,
            bool download). The last parameter is True, when progress is about
            download, False if upload. If no transfer information is declared,
            total might be -1.
        @param transfer_callback: callable
        """
        self._transfer_callback = callback

    @property
    def _settings(self):
        """
        Get SystemSettings instance
        """
        if self.__settings is None:
            self.__settings = self._entropy.Settings()
        return self.__settings

    @property
    def _arch(self):
        """
        Get currently running Entropy architecture
        """
        return self._settings['repositories']['arch']

    @property
    def _product(self):
        """
        Get currently running Entropy product
        """
        return self._settings['repositories']['product']

    @property
    def _branch(self):
        """
        Get currently running Entropy branch
        """
        return self._settings['repositories']['branch']

    @property
    def _authstore(self):
        """
        Repository authentication configuration storage interface.
        Makes possible to retrieve on-disk stored user credentials.
        """
        if self.__auth_storage is None:
            self.__auth_storage = AuthenticationStorage()
        return self.__auth_storage

    @property
    def _cacher(self):
        if self.__cacher is None:
            self.__cacher = EntropyCacher()
        return self.__cacher

    def _generate_user_agent(self, function_name):
        """
        Generate a standard (entropy services centric) HTTP User Agent.
        """
        uname = os.uname()
        user_agent = "Entropy.Services/%s (compatible; %s; %s: %s %s %s)" % (
            etpConst['entropyversion'],
            "Entropy",
            function_name,
            uname[0],
            uname[4],
            uname[2],
        )
        return user_agent

    def _encode_multipart_form(self, params, file_params, boundary):
        """
        Encode parameters and files into a valid HTTP multipart form data.
        NOTE: this method loads the whole file in RAM, HTTP post doesn't work
        well for big files anyway.
        """
        tmp_fd, tmp_path = tempfile.mkstemp()
        tmp_f = os.fdopen(tmp_fd, "ab+")
        tmp_f.truncate(0)
        crlf = '\r\n'
        for key, value in params.items():
            tmp_f.write("--" + boundary + crlf)
            tmp_f.write("Content-Disposition: form-data; name=\"%s\"" % (
                key,))
            tmp_f.write(crlf + crlf + value + crlf)
        for key, (f_name, f_obj) in file_params.items():
            tmp_f.write("--" + boundary + crlf)
            tmp_f.write(
                "Content-Disposition: form-data; name=\"%s\"; filename=\"%s\"" % (
                    key, f_name,))
            tmp_f.write(crlf)
            tmp_f.write("Content-Type: application/octet-stream" + crlf)
            tmp_f.write("Content-Transfer-Encoding: binary" + crlf + crlf)
            f_obj.seek(0)
            while True:
                chunk = f_obj.read(65536)
                if not chunk:
                    break
                tmp_f.write(chunk)
            tmp_f.write(crlf)

        tmp_f.write("--" + boundary + "--" + crlf + crlf)
        tmp_f.flush()
        return tmp_f, tmp_path

    def _generic_post_handler(self, function_name, params, file_params):
        """
        Given a function name and the request data (dict format), do the actual
        HTTP request and return the response object to caller.
        WARNING: params and file_params dict keys must be ASCII string only.

        @param function_name: name of the function that called this method
        @type function_name: string
        @param params: POST parameters
        @type params: dict
        @param file_params: mapping composed by file names as key and tuple
            composed by (file_name, file object) as values
        @type file_params: dict
        @return: tuple composed by the server response string or None
            (in case of empty response) and the HTTPResponse object (useful
                for checking response status)
        @rtype: tuple
        """
        multipart_boundary = "---entropy.services,boundary---"
        request_path = self._request_path.rstrip("/") + "/" + function_name
        const_debug_write(__name__,
            "WebService _generic_post_handler, calling: %s at %s -- %s,"
            " tx_callback: %s" % (self._request_host, request_path,
                params, self._transfer_callback,))
        connection = None
        try:
            if self._request_protocol == "http":
                connection = httplib.HTTPConnection(self._request_host,
                    timeout = self._default_timeout_secs)
            elif self._request_protocol == "https":
                connection = httplib.HTTPSConnection(self._request_host,
                    timeout = self._default_timeout_secs)
            else:
                raise WebService.RequestError("invalid request protocol")

            headers = {
                "Accept": "text/plain",
                "User-Agent": self._generate_user_agent(function_name),
            }

            if file_params is None:
                file_params = {}
            # autodetect file parameters in params
            for k in list(params.keys()):
                if isinstance(params[k], (tuple, list)) \
                    and (len(params[k]) == 2):
                    f_name, f_obj = params[k]
                    if isinstance(f_obj, file):
                        file_params[k] = params[k]
                        del params[k]
                elif const_isunicode(params[k]):
                    # convert to raw string
                    params[k] = const_convert_to_rawstring(params[k],
                        from_enctype = "utf-8")

            body = None
            if not file_params:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                encoded_params = urllib.urlencode(params)
                data_size = len(encoded_params)
                if self._transfer_callback is not None:
                    self._transfer_callback(0, data_size, False)

                if data_size < 65536:
                    connection.request("POST", request_path, encoded_params,
                        headers)
                else:
                    connection.request("POST", request_path, None, headers)
                    sio = StringIO(encoded_params)
                    data_size = len(encoded_params)
                    while True:
                        chunk = sio.read(65535)
                        if not chunk:
                            break
                        try:
                            connection.send(chunk)
                        except socket.error as err:
                            raise WebService.RequestError(err)
                        if self._transfer_callback is not None:
                            self._transfer_callback(sio.tell(),
                                data_size, False)
                # for both ways, send a signal through the callback
                if self._transfer_callback is not None:
                    self._transfer_callback(data_size, data_size, False)

            else:
                headers["Content-Type"] = "multipart/form-data; boundary=" + \
                    multipart_boundary
                body_file, body_fpath = self._encode_multipart_form(params,
                    file_params, multipart_boundary)
                try:
                    data_size = body_file.tell()
                    headers["Content-Length"] = str(data_size)
                    body_file.seek(0)
                    if self._transfer_callback is not None:
                        self._transfer_callback(0, data_size, False)

                    connection.request("POST", request_path, None, headers)
                    while True:
                        chunk = body_file.read(65535)
                        if not chunk:
                            break
                        try:
                            connection.send(chunk)
                        except socket.error as err:
                            raise WebService.RequestError(err)
                        if self._transfer_callback is not None:
                            self._transfer_callback(body_file.tell(),
                                data_size, False)
                    if self._transfer_callback is not None:
                        self._transfer_callback(data_size, data_size, False)
                finally:
                    body_file.close()
                    os.remove(body_fpath)

            response = connection.getresponse()
            total_length = response.getheader("Content-Length", "-1")
            try:
                total_length = int(total_length)
            except ValueError:
                total_length = -1
            outcome = ""
            current_len = 0
            if self._transfer_callback is not None:
                self._transfer_callback(current_len, total_length, True)
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                outcome += chunk
                current_len += len(chunk)
                if self._transfer_callback is not None:
                    self._transfer_callback(current_len, total_length, True)

            if self._transfer_callback is not None:
                self._transfer_callback(total_length, total_length, True)

            if not outcome:
                return None, response
            return outcome, response

        except httplib.HTTPException as err:
            raise WebService.RequestError(err)
        finally:
            if connection is not None:
                connection.close()

    def _setup_credentials(self, request_params):
        """
        This method is automatically called by public API functions to setup
        credentials data if available, otherwise user interaction will be
        triggered by raising WebService.AuthenticationRequired
        """
        creds = self._authstore.get(self._repository_id)
        if creds is None:
            raise WebService.AuthenticationRequired(self._repository_id)
        username, password = creds
        request_params['username'], request_params['password'] = \
            username, password

    def add_credentials(self, username, password):
        """
        Add credentials for this repository and store the information into
        an user-protected location.
        """
        self.__credentials_validated = False
        self._authstore.add(self._repository_id, username, password)

    def validate_credentials(self):
        """
        Validate currently stored credentials (if available) against the
        remote service. If credentials are not available,
        WebService.AuthenticationRequired is raised.
        If credentials are not valid, WebService.AuthenticationFailed is
        raised.

        @raise WebService.AuthenticationRequired: if credentials are not
            available
        @raise WebService.AuthenticationFailed: if credentials are not valid
        """
        if not self.credentials_available():
            raise WebService.AuthenticationRequired("credentials not available")
        if not self.__credentials_validated:
            # this will raise WebService.AuthenticationFailed if credentials
            # are invalid
            self._method_getter("validate_credentials", {}, cache = False,
                require_credentials = True)
            self.__credentials_validated = True

    def credentials_available(self):
        """
        Return whether credentials are stored locally or not.
        Please note that credentials can be stored properly but considered
        invalid remotely.

        @return: True, if credentials are available
        @rtype: bool
        """
        return self._authstore.get(self._repository_id) is not None

    def get_credentials(self):
        """
        Return the username string stored in the authentication storage, if any.
        Otherwise return None.

        @return: the username string stored in the authentication storage
        @rtype: string or None
        """
        creds = self._authstore.get(self._repository_id)
        if creds is not None:
            username, _pass = creds
            return username

    def remove_credentials(self):
        """
        Remove any credential bound to the repository from on-disk storage.

        @return: True, if credentials existed and got removed
        @rtype: bool
        """
        self.__credentials_validated = False
        return self._authstore.remove(self._repository_id)

    CACHE_DIR = os.path.join(etpConst['entropyworkdir'], "websrv_cache")

    def _get_cache_key(self, method, params):
        """
        Return on disk cache file name as key, given a method name and its
        parameters.
        """
        hash_str = repr(params)
        if sys.hexversion >= 0x3000000:
            hash_str = hash_str.encode("utf-8")
        sha = hashlib.sha1()
        sha.update(hash_str)
        return method + "_" + sha.hexdigest()

    def _get_cached(self, cache_key):
        """
        Return an on-disk cached object for given cache key.
        """
        with self._cache_dir_lock:
            return self._cacher.pop(cache_key, cache_dir = WebService.CACHE_DIR)

    def _set_cached(self, cache_key, data):
        """
        Save a cache item to disk.
        """
        with self._cache_dir_lock:
            return self._cacher.save(cache_key, data,
                cache_dir = WebService.CACHE_DIR)

    def _drop_cached(self, method):
        """
        Drop all on-disk cache for given method.
        """
        with self._cache_dir_lock:
            cache_dir = WebService.CACHE_DIR
            for currentdir, subdirs, files in os.walk(cache_dir):
                hostile_files = [os.path.join(currentdir, x) for x in \
                    files if x.startswith(method + "_")]
                for path in hostile_files:
                    try:
                        os.remove(path)
                    except OSError as err:
                        # avoid race conditions
                        if err.errno != errno.ENOENT:
                            raise

    def _method_getter(self, func_name, params, cache = True,
        require_credentials = False, file_params = None):
        """
        Given a function name and request parameters, do all the duties required
        to get a response from the Web Service. This method raises several
        exceptions, that have to be advertised on public methods as well.

        @param func_name: API function name
        @type func_name: string
        @param params: dictionary object that will be converted into a JSON
            request string
        @type params: dict
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword require_credentials: True means that credentials will be added
            to the request, if credentials are not available in the local
            authentication storage, WebService.AuthenticationRequired is
            raised
        @type require_credentials: bool
        @param file_params: mapping composed by file names as key and tuple
            composed by (file_name, file object) as values
        @type file_params: dict
        @return: the JSON response (dict format)
        @rtype: dict
        @raise WebService.UnsupportedParameters: if input parameters are invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occured (error code passed as exception
            argument)
        @raise WebService.AuthenticationRequired: if require_credentials is True
            and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        """
        if require_credentials:
            # this can raise AuthenticationRequired
            self._setup_credentials(params)

        cache_key = None
        if cache:
            cache_key = self._get_cache_key(func_name, params)
            obj = self._get_cached(cache_key)
            if obj is not None:
                const_debug_write(__name__, "WebService.%s(%s) = cached %s" % (
                    func_name, params, obj,))
                return obj
            const_debug_write(__name__, "WebService.%s(%s) = NOT cached" % (
                func_name, params,))

        obj = None
        try:
            json_response, response = self._generic_post_handler(func_name,
                params, file_params)

            http_status = response.status
            if http_status not in (httplib.OK,):
                raise WebService.MethodNotAvailable(http_status)

            # try to convert the JSON response
            try:
                data = json.loads(json_response)
            except (ValueError, TypeError) as err:
                raise WebService.MalformedResponse(err)

            # check API
            if data.get("api_rev") != WebService.SUPPORTED_API_LEVEL:
                raise WebService.UnsupportedAPILevel(data['api_rev'])

            code = data.get("code", -1)
            if code == WebService.WEB_SERVICE_INVALID_CREDENTIALS_CODE:
                # invalid credentials, ask again login data
                raise WebService.AuthenticationFailed(code)
            if code != WebService.WEB_SERVICE_RESPONSE_CODE_OK:
                raise WebService.MethodResponseError(code)

            if "r" not in data:
                raise WebService.MalformedResponse("r not found")
            obj = data["r"]
            return obj

        finally:
            if cache and (obj is not None):
                # store cache
                if cache_key is None:
                    cache_key = self._get_cache_key(func_name, params)
                self._set_cached(cache_key, obj)

    def service_available(self, cache = True):
        """
        Return whether the Web Service is correctly able to answer our requests.

        @raise WebService.UnsupportedParameters: if input parameters are invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occured (error code passed as exception
            argument)
        @raise WebService.AuthenticationRequired: if require_credentials is True
            and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        """
        params = locals().copy()
        params.pop("self")
        params.pop("cache")
        return self._method_getter("service_available", params, cache = cache,
            require_credentials = False)

    def data_send_available(self):
        """
        Return whether data send is correctly working. A temporary file with
        random content is sent to the service, that would need to calculate
        its md5 hash. For security reason, data will be accepted remotely if,
        and only if its size is < 256 bytes.
        """
        md5 = hashlib.md5()
        test_str = const_convert_to_rawstring("")
        for x in range(256):
            test_str += chr(x)
        md5.update(test_str)
        expected_hash = md5.hexdigest()
        func_name = "data_send_available"

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with os.fdopen(tmp_fd, "ab+") as tmp_f:
                tmp_f.write(test_str)
                tmp_f.seek(0)
                params = {
                    "test_param": "hello",
                }
                file_params = {
                    "test_file": ("test_file.txt", tmp_f),
                }
                remote_hash = self._method_getter(func_name, params,
                    cache = False, require_credentials = False,
                    file_params = file_params)
        finally:
            os.remove(tmp_path)

        const_debug_write(__name__,
            "WebService.%s, expected: %s, got: %s" % (
                func_name, repr(expected_hash), repr(remote_hash),))
        return expected_hash == remote_hash


class AuthenticationStorage(Singleton):
    """
    Entropy Web Service authentication credentials storage class.
    """

    _AUTH_FILE = ".entropy/id_entropy"

    def init_singleton(self):

        self.__dump_lock = threading.Lock()
        # not loaded, load at very last moment
        self.__store = None

        # setup auth file path
        home = os.getenv("HOME")
        self.__auth_file = None
        if home is not None:
            if os.path.isdir(home) and os.access(home, os.W_OK):
                auth_file = os.path.join(home,
                    AuthenticationStorage._AUTH_FILE)
                auth_dir = os.path.dirname(auth_file)
                if not os.path.isdir(auth_dir):
                    self.__auth_file = auth_file
                    try:
                        os.makedirs(auth_dir, 0o700)
                        const_setup_file(auth_dir, etpConst['entropygid'],
                            0o700)
                    except (OSError, IOError):
                        # ouch, no permissions
                        self.__auth_file = None

        if self.__auth_file is None:
            # cannot reliably store an auth file, falling back
            # to a private temp file
            tmp_fd, tmp_path = tempfile.mkstemp()
            os.close(tmp_fd)
            self.__auth_file = tmp_path


    @property
    def _authstore(self):
        """
        Authentication data object automatically loaded from disk if needed.
        """
        if self.__store is None:
            store = entropy.dump.loadobj(self.__auth_file,
                complete_path = True)
            if store is None:
                store = {}
            elif not isinstance(store, dict):
                store = {}
            self.__store = store
        return self.__store

    def save(self):
        """
        Save currently loaded authentication configuration to disk.

        @return: True, if save was effectively run
        @rtype: bool
        """
        with self.__dump_lock:
            entropy.dump.dumpobj(self.__auth_file, self._authstore,
                complete_path = True, custom_permissions = 0o600)
        # make sure
        try:
            const_setup_file(self.__auth_file, etpConst['entropygid'],
                0o600)
            return True
        except (OSError, IOError):
            return False

    def add(self, repository_id, username, password):
        """
        Add authentication credentials to Authentication configuration.

        @param repository_id: repository identifier
        @type repository_id: string
        @param username: the username
        @type username: string
        @param password: the password
        @type password: string
        """
        self._authstore[repository_id] = {
            'username': username,
            'password': password,
        }

    def remove(self, repository_id):
        """
        Remove any credential for given repository identifier.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: True, if removal went fine (if there was something to remove)
        @rtype: bool
        """
        try:
            del self._authstore[repository_id]
            return True
        except KeyError:
            return False

    def get(self, repository_id):
        """
        Get authentication credentials for given repository identifier.

        @return: tuple composed by username, password, or None, if credentials
        are not found
        @rtype: tuple or None
        """
        data = self._authstore.get(repository_id)
        if data is None:
            return None
        return data['username'], data['password']
