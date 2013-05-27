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
import threading
import hashlib

import socket

from entropy.const import const_is_python3, const_convert_to_rawstring, \
    const_get_int, const_mkstemp

if const_is_python3():
    import http.client as httplib
    from io import StringIO
    import urllib.parse as urllib_parse
else:
    import httplib
    from cStringIO import StringIO
    import urllib as urllib_parse

import entropy.dump
from entropy.core import Singleton
from entropy.cache import EntropyCacher
from entropy.const import const_debug_write, const_setup_file, etpConst, \
    const_convert_to_rawstring, const_isunicode, const_isstring, \
    const_convert_to_unicode, const_isstring, const_debug_enabled
from entropy.core.settings.base import SystemSettings
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
            raise WebServiceFactory.InvalidWebServiceFactory(
                "invalid web_service_class")
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

    # Default common Web Service responses, please use these when
    # implementing your web service
    WEB_SERVICE_RESPONSE_CODE_OK = 200
    WEB_SERVICE_INVALID_CREDENTIALS_CODE = 450
    WEB_SERVICE_INVALID_REQUEST_CODE = 400
    WEB_SERVICE_NOT_FOUND_CODE = 404
    WEB_SERVICE_RESPONSE_ERROR_CODE = 503


    class WebServiceException(EntropyException):
        """
        Base WebService exception class.
        """
        def __init__(self, value, method = None, message = None):
            self.value = value
            self.method = method
            self.message = message
            Exception.__init__(self)

        def __get_method(self):
            if self.method is None:
                method = const_convert_to_unicode("")
            else:
                method = const_convert_to_unicode(self.method)
            return method

        def __get_message(self):
            if self.message is None:
                message = const_convert_to_unicode("")
            else:
                message = const_convert_to_unicode(self.message)
            return message

        def __unicode__(self):
            method = self.__get_method()
            message = self.__get_message()
            if const_isstring(self.value):
                return const_convert_to_unicode(method + " " + self.value) \
                    + ", " + message
            return const_convert_to_unicode(method + " " + repr(self.value)) \
                 + ", " + message

        def __str__(self):
            method = self.__get_method()
            message = self.__get_message()
            if const_isstring(self.value):
                return method + " " + self.value + ", " + message
            return method + " " + repr(self.value) + ", " + message

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

    class CacheMiss(WebServiceException):
        """
        If the request is not available in the on-disk cache.
        """

    def __init__(self, entropy_client, repository_id):
        """
        WebService constructor.
        NOTE: This base class must NOT use any Entropy Client specific method
        and MUST rely on what is provided by it's parent class TextInterface.

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
        self._default_timeout_secs = 10.0
        self.__credentials_validated = False
        # if this is set, cache will be considered invalid if older than
        self._cache_aging_days = None

        config = self.config(repository_id)
        if config is None:
            raise WebService.UnsupportedService("unsupported service [1]")

        remote_url = config['url']
        if remote_url is None:
            raise WebService.UnsupportedService("unsupported service [2]")
        url_obj = config['_url_obj']

        self._request_url = remote_url
        self._request_protocol = url_obj.scheme
        self._request_host = url_obj.netloc
        self._request_path = url_obj.path
        self._config = config

        const_debug_write(__name__, "WebService loaded, url: %s" % (
            self._request_url,))

    @classmethod
    def config(cls, repository_id):
        """
        Return the WebService configuration for the given repository.
        The object returned is a dictionary containing the following
        items:
          - url: the Entropy WebService base URL (or None, if not supported)
          - update_eapi: the maximum supported EAPI for repository updates.
          - repo_eapi: the maximum supported EAPI for User Generate Content.

        @param repository_id: repository identifier
        @type repository_id: string
        """
        settings = SystemSettings()
        _repository_data = settings['repositories']['available'].get(
            repository_id)
        if _repository_data is None:
            const_debug_write(__name__, "WebService.config error: no repo")
            return None

        web_services_conf = _repository_data.get('webservices_config')
        if web_services_conf is None:
            const_debug_write(__name__, "WebService.config error: no metadata")
            return None

        data = {
            'url': None,
            '_url_obj': None,
            'update_eapi': None,
            'repo_eapi': None,
            }

        content = []
        try:
            content += entropy.tools.generic_file_content_parser(
                web_services_conf, encoding = etpConst['conf_encoding'])
        except (OSError, IOError) as err:
            const_debug_write(__name__, "WebService.config error: %s" % (
                err,))
            return None

        if not content:
            const_debug_write(
                __name__, "WebService.config error: empty config")
            return None

        remote_url = content.pop(0)
        if remote_url == "-":  # as per specs
            remote_url = None
        elif not remote_url:
            remote_url = None
        data['url'] = remote_url

        if data['url']:
            url_obj = entropy.tools.spliturl(data['url'])
            if url_obj.scheme in WebService.SUPPORTED_URL_SCHEMAS:
                data['_url_obj'] = url_obj
            else:
                data['url'] = None

        for line in content:
            for k in ("UPDATE_EAPI", "REPO_EAPI"):
                if line.startswith(k + "="):
                    try:
                        data[k.lower()] = int(line.split("=", 1)[-1])
                    except (IndexError, ValueError):
                        pass

        return data

    def _set_timeout(self, secs):
        """
        Override default timeout setting a new one (in seconds).
        """
        self._default_timeout_secs = float(secs)

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
            self.__settings = SystemSettings()
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
        def _cast_to_str(value):
            if value is None:
                return const_convert_to_rawstring("")
            elif isinstance(value, (int, float, long)):
                return const_convert_to_rawstring(value)
            elif isinstance(value, (list, tuple)):
                return repr(value)
            return value

        tmp_fd, tmp_path = const_mkstemp(prefix="_encode_multipart_form")
        tmp_f = os.fdopen(tmp_fd, "ab+")
        tmp_f.truncate(0)
        crlf = '\r\n'
        for key, value in params.items():
            tmp_f.write("--" + boundary + crlf)
            tmp_f.write("Content-Disposition: form-data; name=\"%s\"" % (
                key,))
            tmp_f.write(crlf + crlf + _cast_to_str(value) + crlf)
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

    def _generic_post_handler(self, function_name, params, file_params,
        timeout):
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
        @param timeout: socket timeout
        @type timeout: float
        @return: tuple composed by the server response string or None
            (in case of empty response) and the HTTPResponse object (useful
                for checking response status)
        @rtype: tuple
        """
        if timeout is None:
            timeout = self._default_timeout_secs
        multipart_boundary = "---entropy.services,boundary---"
        request_path = self._request_path.rstrip("/") + "/" + function_name
        const_debug_write(__name__,
            "WebService _generic_post_handler, calling: %s at %s -- %s,"
            " tx_callback: %s, timeout: %s" % (self._request_host, request_path,
                params, self._transfer_callback, timeout,))
        connection = None
        try:
            if self._request_protocol == "http":
                connection = httplib.HTTPConnection(self._request_host,
                    timeout = timeout)
            elif self._request_protocol == "https":
                connection = httplib.HTTPSConnection(self._request_host,
                    timeout = timeout)
            else:
                raise WebService.RequestError("invalid request protocol",
                    method = function_name)

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
                elif not const_isstring(params[k]):
                    # invalid ?
                    if params[k] is None:
                        # will be converted to ""
                        continue
                    int_types = const_get_int()
                    supported_types = (float, list, tuple) + int_types
                    if not isinstance(params[k], supported_types):
                        raise WebService.UnsupportedParameters(
                            "%s is unsupported type %s" % (k, type(params[k])))
                    list_types = (list, tuple)
                    if isinstance(params[k], list_types):
                        # not supporting nested lists
                        non_str = [x for x in params[k] if not \
                            const_isstring(x)]
                        if non_str:
                            raise WebService.UnsupportedParameters(
                                "%s is unsupported type %s" % (k,
                                    type(params[k])))

            body = None
            if not file_params:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                encoded_params = urllib_parse.urlencode(params)
                data_size = len(encoded_params)
                if self._transfer_callback is not None:
                    self._transfer_callback(0, data_size, False)

                if data_size < 65536:
                    try:
                        connection.request("POST", request_path, encoded_params,
                            headers)
                    except socket.error as err:
                        raise WebService.RequestError(err,
                            method = function_name)
                else:
                    try:
                        connection.request("POST", request_path, None, headers)
                    except socket.error as err:
                        raise WebService.RequestError(err,
                            method = function_name)
                    sio = StringIO(encoded_params)
                    data_size = len(encoded_params)
                    while True:
                        chunk = sio.read(65535)
                        if not chunk:
                            break
                        try:
                            connection.send(chunk)
                        except socket.error as err:
                            raise WebService.RequestError(err,
                                method = function_name)
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

                    try:
                        connection.request("POST", request_path, None, headers)
                    except socket.error as err:
                        raise WebService.RequestError(err,
                            method = function_name)
                    while True:
                        chunk = body_file.read(65535)
                        if not chunk:
                            break
                        try:
                            connection.send(chunk)
                        except socket.error as err:
                            raise WebService.RequestError(err,
                                method = function_name)
                        if self._transfer_callback is not None:
                            self._transfer_callback(body_file.tell(),
                                data_size, False)
                    if self._transfer_callback is not None:
                        self._transfer_callback(data_size, data_size, False)
                finally:
                    body_file.close()
                    os.remove(body_fpath)

            try:
                response = connection.getresponse()
            except socket.error as err:
                raise WebService.RequestError(err,
                    method = function_name)
            const_debug_write(__name__, "WebService.%s(%s), "
                "response header: %s" % (
                    function_name, params, response.getheaders(),))
            total_length = response.getheader("Content-Length", "-1")
            try:
                total_length = int(total_length)
            except ValueError:
                total_length = -1
            outcome = const_convert_to_rawstring("")
            current_len = 0
            if self._transfer_callback is not None:
                self._transfer_callback(current_len, total_length, True)
            while True:
                try:
                    chunk = response.read(65536)
                except socket.error as err:
                    raise WebService.RequestError(err,
                        method = function_name)
                if not chunk:
                    break
                outcome += chunk
                current_len += len(chunk)
                if self._transfer_callback is not None:
                    self._transfer_callback(current_len, total_length, True)

            if self._transfer_callback is not None:
                self._transfer_callback(total_length, total_length, True)

            if const_is_python3():
                outcome = const_convert_to_unicode(outcome)
            if not outcome:
                return None, response
            return outcome, response

        except httplib.HTTPException as err:
            raise WebService.RequestError(err,
                method = function_name)
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

    def _setup_generic_params(self, request_params):
        """
        This methods adds some generic parameters to the HTTP request metadata.
        Any parameter added by this method is prefixed with __, to avoid
        name collisions.
        """
        request_params["__repository_id__"] = self._repository_id

    def enable_cache_aging(self, days):
        """
        Turn on on-disk cache aging support. If cache is older than given
        days, it will be removed and considered invalid.
        """
        self._cache_aging_days = int(days)

    def add_credentials(self, username, password):
        """
        Add credentials for this repository and store the information into
        an user-protected location.
        """
        self.__credentials_validated = False
        self._authstore.add(self._repository_id, username, password)
        self._authstore.save()

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
        res = self._authstore.remove(self._repository_id)
        self._authstore.save()
        return res

    CACHE_DIR = os.path.join(etpConst['entropyworkdir'], "websrv_cache")

    def _get_cache_key(self, method, params):
        """
        Return on disk cache file name as key, given a method name and its
        parameters.
        """
        sorted_data = [(x, params[x]) for x in sorted(params.keys())]
        hash_str = repr(sorted_data) + ", " + self._request_url
        if const_is_python3():
            hash_str = hash_str.encode("utf-8")
        sha = hashlib.sha1()
        sha.update(hash_str)
        return method + "_" + sha.hexdigest()

    def _get_cached(self, cache_key):
        """
        Return an on-disk cached object for given cache key.
        """
        with self._cache_dir_lock:
            return self._cacher.pop(
                cache_key, cache_dir = WebService.CACHE_DIR,
                aging_days = self._cache_aging_days)

    def _set_cached(self, cache_key, data):
        """
        Save a cache item to disk.
        """
        with self._cache_dir_lock:
            try:
                return self._cacher.save(cache_key, data,
                    cache_dir = WebService.CACHE_DIR)
            except IOError as err:
                # IOError is raised when cache cannot be written to disk
                if const_debug_enabled():
                    const_debug_write(__name__,
                        "WebService._set_cached(%s) = cache store error: %s" % (
                            cache_key, repr(err),))

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

    def _method_cached(self, func_name, params, cache_key = None):
        """
        Try to fetch on-disk cached object and return it. If error or not
        found, None is returned.
        """
        # setup generic request parameters
        self._setup_generic_params(params)

        if cache_key is None:
            cache_key = self._get_cache_key(func_name, params)
        return self._get_cached(cache_key)

    def _method_getter(self, func_name, params, cache = True,
        cached = False, require_credentials = False, file_params = None,
        timeout = None):
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
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @keyword require_credentials: True means that credentials will be added
            to the request, if credentials are not available in the local
            authentication storage, WebService.AuthenticationRequired is
            raised
        @type require_credentials: bool
        @param file_params: mapping composed by file names as key and tuple
            composed by (file_name, file object) as values
        @type file_params: dict
        @param timeout: provide specific socket timeout
        @type timeout: float
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
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        cache_key = self._get_cache_key(func_name, params)
        if cache or cached:
            # this does call: _setup_generic_params()
            obj = self._method_cached(func_name, params, cache_key = cache_key)
            if (obj is None) and cached:
                if const_debug_enabled():
                    const_debug_write(__name__,
                        "WebService.%s(%s) = cache miss: %s" % (
                            func_name, params, cache_key,))
                raise WebService.CacheMiss(
                    WebService.WEB_SERVICE_NOT_FOUND_CODE, method = func_name)
            if obj is not None:
                if const_debug_enabled():
                    const_debug_write(__name__,
                        "WebService.%s(%s) = CACHED!" % (
                            func_name, params,))
                return obj
            if const_debug_enabled():
                const_debug_write(__name__, "WebService.%s(%s) = NOT cached" % (
                    func_name, params,))
        else:
            self._setup_generic_params(params)

        if require_credentials:
            # this can raise AuthenticationRequired
            self._setup_credentials(params)

        obj = None
        try:
            json_response, response = self._generic_post_handler(func_name,
                params, file_params, timeout)

            http_status = response.status
            if http_status not in (httplib.OK,):
                raise WebService.MethodNotAvailable(http_status,
                    method = func_name)

            # try to convert the JSON response
            try:
                data = json.loads(json_response)
            except (ValueError, TypeError) as err:
                raise WebService.MalformedResponse(err,
                    method = func_name)

            # check API
            if data.get("api_rev") != WebService.SUPPORTED_API_LEVEL:
                raise WebService.UnsupportedAPILevel(data['api_rev'],
                    method = func_name, message = data.get("message"))

            code = data.get("code", -1)
            if code == WebService.WEB_SERVICE_INVALID_CREDENTIALS_CODE:
                # invalid credentials, ask again login data
                raise WebService.AuthenticationFailed(code,
                    method = func_name, message = data.get("message"))
            if code != WebService.WEB_SERVICE_RESPONSE_CODE_OK:
                raise WebService.MethodResponseError(code,
                    method = func_name, message = data.get("message"))

            if "r" not in data:
                raise WebService.MalformedResponse("r not found",
                    method = func_name, message = data.get("message"))
            obj = data["r"]

            if const_debug_enabled():
                const_debug_write(__name__, "WebService.%s(%s) = fetched!" % (
                    func_name, params,))
            return obj

        finally:
            if obj is not None:
                # store cache
                self._set_cached(cache_key, obj)

    def service_available(self, cache = True, cached = False):
        """
        Return whether the Web Service is correctly able to answer our requests.

        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: True, if service is available
        @rtype: bool

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
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        params = locals().copy()
        params.pop("self")
        params.pop("cache")
        return self._method_getter("service_available", params, cache = cache,
            cached = cached, require_credentials = False)

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

        tmp_fd, tmp_path = const_mkstemp(prefix="data_send_available")
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

    def _get_authfile(self):
        """
        Try to get the auth file. If it fails, return None.
        """
        # setup auth file path
        home = os.getenv("HOME")
        auth_file = None
        if home is not None:
            if os.path.isdir(home) and os.access(home, os.W_OK):
                auth_file = os.path.join(home,
                    AuthenticationStorage._AUTH_FILE)
                auth_dir = os.path.dirname(auth_file)
                if not os.path.isdir(auth_dir):
                    try:
                        os.makedirs(auth_dir, 0o700)
                        const_setup_file(auth_dir, etpConst['entropygid'],
                            0o700)
                    except (OSError, IOError):
                        # ouch, no permissions
                        auth_file = None
        return auth_file

    @property
    def _authstore(self):
        """
        Authentication data object automatically loaded from disk if needed.
        """
        if self.__store is None:
            auth_file = self._get_authfile()
            store = {}
            if auth_file is not None:
                store = entropy.dump.loadobj(auth_file, complete_path = True)
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
            auth_file = self._get_authfile()
            if auth_file is not None:
                entropy.dump.dumpobj(auth_file, self._authstore,
                    complete_path = True, custom_permissions = 0o600)
        # make sure
        if auth_file is not None:
            try:
                const_setup_file(auth_file, etpConst['entropygid'],
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
