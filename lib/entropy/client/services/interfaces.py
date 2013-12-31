# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Client Repository Web Services Client interface}.

"""
__all__ = ["ClientWebServiceFactory", "ClientWebService", "Document",
    "DocumentList", "DocumentFactory", "RepositoryWebServiceFactory",
    "RepositoryWebService"]

import sys
import os
import base64
import hashlib
import time
import codecs

from entropy.const import const_is_python3, const_debug_write, \
    const_dir_writable

if const_is_python3():
    from io import StringIO
else:
    from cStringIO import StringIO

from entropy.const import const_get_stringtype, etpConst, const_setup_perms, \
    const_convert_to_rawstring, const_convert_to_unicode, const_mkstemp
from entropy.i18n import _
from entropy.services.client import WebServiceFactory, WebService
from entropy.fetchers import UrlFetcher

class Document(dict):
    """
    User Generated Content Document object. It inherits a dictionary and
    contains metadata bound to a single content item (such as, a user comment,
    image, etc).
    Since the metadata format is "volatile" at the moment, you should use
    Document.get() to retrieve metadata objects (this is a hash table) rather
    than relying on __getitem__ (using obj[item_key]).
    """

    # basic document types supported
    UNKNOWN_TYPE_ID = -1
    COMMENT_TYPE_ID = 1
    # BBCODE_TYPE_ID = 2
    IMAGE_TYPE_ID = 3
    FILE_TYPE_ID = 4
    VIDEO_TYPE_ID = 5
    # This is a new ID, new documents will have this
    ICON_TYPE_ID = 6

    SUPPORTED_TYPES = (COMMENT_TYPE_ID, IMAGE_TYPE_ID, FILE_TYPE_ID,
        VIDEO_TYPE_ID, ICON_TYPE_ID)

    DESCRIPTION_PLURAL = {
        UNKNOWN_TYPE_ID: _("Unknown documents"),
        COMMENT_TYPE_ID: _('Comments'),
        # BBCODE_TYPE_ID: _('BBcode Documents'),
        IMAGE_TYPE_ID: _('Images/Screenshots'),
        FILE_TYPE_ID: _('Generic Files'),
        VIDEO_TYPE_ID: _('Videos'),
        ICON_TYPE_ID: _('Icons'),
    }
    DESCRIPTION_SINGULAR = {
        UNKNOWN_TYPE_ID: _("Unknown document"),
        COMMENT_TYPE_ID: _('Comment'),
        # BBCODE_TYPE_ID: _('BBcode Document'),
        IMAGE_TYPE_ID: _('Image/Screenshot'),
        FILE_TYPE_ID: _('Generic File'),
        VIDEO_TYPE_ID: _('Video'),
        ICON_TYPE_ID: _('Icon'),
    }

    # backward compatibility
    PACKAGE_ICON_TITLE_ID = "__icon__"

    # Document hash table key pointing to document repository id
    # see Document.repository_id()
    DOCUMENT_REPOSITORY_ID = "repository_id"

    # Document hash table key pointing to document id
    # see Document.document_id()
    DOCUMENT_DOCUMENT_ID = "document_id"

    # Document hash table key pointing to document type id
    # see Document.document_type_id()
    DOCUMENT_DOCUMENT_TYPE_ID = "document_type_id"

    # Document hash table key pointing to document data
    # see Document.document_data()
    DOCUMENT_DATA_ID = "ddata"

    # Document hash table key for the document title
    DOCUMENT_TITLE_ID = "title"

    # Document hash table key for the document description
    DOCUMENT_DESCRIPTION_ID = "description"

    # Document hash table key pointing to document keywords (tags...)
    # see Document.document_keywords()
    DOCUMENT_KEYWORDS_ID = "keywords"

    # Document hash table key pointing to document timestamp (float)
    DOCUMENT_TIMESTAMP_ID = "ts"

    # Document hash table key pointing to document URL
    DOCUMENT_URL_ID = "url"

    def __init__(self, repository_id, document_id, document_type_id):
        """
        Document constructor.

        @param repository_id: repository identifier
        @type repository_id: string
        @param document_id: document unique identifier
        @type document_id: int
        @param document_id: document type identifier
        @type document_id: int
        """
        self._document_type_revmap = {
            1: Document.COMMENT_TYPE_ID,
            # 2: Document.BBCODE_TYPE_ID,
            3: Document.IMAGE_TYPE_ID,
            4: Document.FILE_TYPE_ID,
            5: Document.VIDEO_TYPE_ID,
            6: Document.ICON_TYPE_ID,
        }
        obj = {
            Document.DOCUMENT_REPOSITORY_ID: repository_id,
            Document.DOCUMENT_DOCUMENT_ID: document_id,
            Document.DOCUMENT_DOCUMENT_TYPE_ID: document_type_id,
        }
        self.update(obj)
        self._add_base_metadata()

    def _add_base_metadata(self):
        """
        Add base metadata to Document object.
        """
        if Document.DOCUMENT_TIMESTAMP_ID not in self:
            self[Document.DOCUMENT_TIMESTAMP_ID] = repr(time.time())

    def repository_id(self):
        """
        Return the currently set repository identifier.

        @return: the repository identifier
        @rtype: string
        """
        return self[Document.DOCUMENT_REPOSITORY_ID]

    def document_id(self):
        """
        Return the currently set document unique identifier.

        @return: document unique identifier
        @rtype: int
        """
        return self[Document.DOCUMENT_DOCUMENT_ID]

    def document_type(self):
        """
        Return the document type identifier, which is always one of:
        Document.UNKNOWN_TYPE_ID, Document.COMMENT_TYPE_ID,
        Document.BBCODE_TYPE_ID, Document.IMAGE_TYPE_ID,
        Document.FILE_TYPE_ID, Document.VIDEO_TYPE_ID

        @return: the document type identifier
        @rtype: int
        """
        return self._document_type_revmap.get(
            self[Document.DOCUMENT_DOCUMENT_TYPE_ID],
            Document.UNKNOWN_TYPE_ID)

    def document_data(self):
        """
        Return encapsulated document data. This is an opaque object, usually
        string, that depends on the document type.
        If there is no document data, None is returned.

        @return: document data
        @rtype: object or None
        """
        return self.get(Document.DOCUMENT_DATA_ID)

    def document_keywords(self):
        """
        Return a string containing space separated keywords bound to this
        document.
        string is always returned, even if metadatum is not available.

        @return: document keywords
        @rtype: string
        """
        return self.get(Document.DOCUMENT_KEYWORDS_ID, "")

    def document_timestamp(self):
        """
        Return the document timestamp. If value is not available (unlikely)
        the returned value will be 0.0.

        @return: document timestamp
        @rtype: float
        """
        return self.get(Document.DOCUMENT_TIMESTAMP_ID, 0.0)

    def document_url(self):
        """
        Return the document url, if any.

        @return: document URL
        @rtype: string or None
        """
        return self.get(Document.DOCUMENT_URL_ID)

    def is_icon(self):
        """
        Return whether this Document is an Icon document.

        @return: True, if Document is representing an icon
        @rtype: bool
        """
        if self.document_type() == Document.ICON_TYPE_ID:
            return True
        # backward compatibility
        if not self.is_image():
            return False
        if self.get(Document.DOCUMENT_TITLE_ID) == \
            Document.PACKAGE_ICON_TITLE_ID:
            return True
        return False

    def is_image(self):
        """
        Return whether this Document is an Image document.

        @return: True, if Document is representing an image
        @rtype: bool
        """
        return self.document_type() == Document.IMAGE_TYPE_ID

    def is_comment(self):
        """
        Return whether this Document is a Comment document.

        @return: True, if Document is representing a Comment
        @rtype: bool
        """
        return self.document_type() == Document.COMMENT_TYPE_ID

    def is_file(self):
        """
        Return whether this Document is a File document.

        @return: True, if Document is representing a File
        @rtype: bool
        """
        return self.document_type() == Document.FILE_TYPE_ID

    def is_video(self):
        """
        Return whether this Document is a Video document.

        @return: True, if Document is representing a Video
        @rtype: bool
        """
        return self.document_type() == Document.VIDEO_TYPE_ID

    def local_document(self):
        """
        Return the local document data file path. This is where the fetched
        document data (pointed at "url" metadatum) should be placed.
        If the file is available, it means that the document data has been
        already fetched on disk.
        This method can return None, in case there is no URL associated with it.

        @return: the local document data file path
        @rtype: string or None
        """
        url = self.document_url()
        if url is None:
            return None
        return os.path.join(WebService.CACHE_DIR,
            "documents", self.repository_id(),
            str(self.document_id()),
            base64.urlsafe_b64encode(url))

class DocumentList(list):
    """
    DocumentList is a list object providing extra methods for obtaining extra
    document list statuses, such as the number of elements found, the current
    elements list offset, and if there are more elements on the remote service.
    """

    def __init__(self, package_name, has_more, offset):
        """
        DocumentList constructor.

        @param package_name: package name string
        @type package_name: string
        @param has_more: True, if there are more documents available
        @type has_more: bool
        @param offset: list offset used by remote service
        @type offset: int
        """
        list.__init__(self)
        self._package_name = package_name
        self._has_more = has_more
        self._offset = offset

    def package_name(self):
        """
        Return the package name bound to this object.

        @return: the package name
        @rtype: string
        """
        return self._package_name

    def offset(self):
        """
        Return the used offset for fetching this list.

        @return: the used offset
        @rtype: int
        """
        return self._offset

    def has_more(self):
        """
        Return the amount of documents available after those listed here.

        @return: the amount of documents still available on the service,
            given the current offset
        @rtype: int
        """
        return self._has_more


class DocumentFactory(object):
    """
    Class to generate valid, new Document objects.
    """

    # Document hash table key for the document username
    DOCUMENT_USERNAME_ID = "username"

    # Payload metadatum is only available on temporary, to-be-uploaded
    # Document objects. Can contain a file object or any other pointer
    # to a serializable resource.
    DOCUMENT_PAYLOAD_ID = "payload"

    # Maximum string length, used for input validation
    MAX_STRING_LENGTH = 4000

    def __init__(self, repository_id):
        """
        DocumentFactory constructor.

        @param repository_id: repository identifier
        @type repository_id: string
        """
        self._repository_id = repository_id

    def _validate_strings(self, *strings):
        """
        Validate input strings.

        @raise AssertionError: if one of the input objects is invalid
        """
        for string in strings:
            if not isinstance(string, const_get_stringtype()):
                raise AssertionError("invalid string type detected")
            if len(string) > DocumentFactory.MAX_STRING_LENGTH:
                raise AssertionError("string is too long")

    def _validate_string_list(self, string_list):
        """
        Validate input string list.

        @raise AttributeError: if one of the input objects is invalid
        """
        self._validate_strings(*string_list)

    def _validate_file_object(self, f_obj):
        """
        Validate input file object.
        """
        if not isinstance(f_obj, file):
            raise AssertionError("not a file object")
        if f_obj.tell() != 0:
            raise AssertionError("file position != 0")
        if f_obj.closed:
            raise AssertionError("file object is closed")
        if "w" in f_obj.mode:
            raise AssertionError("file object wrong file mode")

    def comment(self, username, comment, title, keywords):
        """
        Generate a new Comment Document.

        @param username: username of the owner of the Document
        @type username: string
        @param comment: comment text
        @type comment: string
        @param title: comment title
        @type title: string
        @param keywords: space separated string containing keywords
        @type keywords: string
        @return: a new Document object
        @rtype: Document
        """
        self._validate_strings(username, comment, title)
        doc = Document(self._repository_id, None, Document.COMMENT_TYPE_ID)
        doc[DocumentFactory.DOCUMENT_USERNAME_ID] = username
        doc[Document.DOCUMENT_DATA_ID] = comment
        doc[Document.DOCUMENT_TITLE_ID] = title
        doc[Document.DOCUMENT_KEYWORDS_ID] = keywords
        return doc

    def image(self, username, file_object, title, description, keywords):
        """
        Generate a new Image Document.

        @param username: username of the owner of the Document
        @type username: string
        @param file_object: file object pointing to the image file data. Note
            that this resource must be closed by the caller once the object
            lifecycle is over. Not doing so will cause the application running
            out of resources, leading to crashes. To retrieve the filename,
            the "name" attribute is read, this won't work for fdopened files.
        @type file_object: string
        @param title: comment title
        @type title: string
        @param keywords: space separated string containing keywords
        @type keywords: string
        @return: a new Document object
        @rtype: Document
        """
        self._validate_strings(username, title, description)
        self._validate_string_list(keywords)
        self._validate_file_object(file_object)
        doc = Document(self._repository_id, None, Document.IMAGE_TYPE_ID)
        doc[DocumentFactory.DOCUMENT_USERNAME_ID] = username
        doc[DocumentFactory.DOCUMENT_PAYLOAD_ID] = \
            (os.path.basename(file_object.name), file_object)
        doc[Document.DOCUMENT_TITLE_ID] = title
        doc[Document.DOCUMENT_DESCRIPTION_ID] = description
        doc[Document.DOCUMENT_KEYWORDS_ID] = keywords
        return doc

    def icon(self, username, file_object, title, description, keywords):
        """
        Generate a new Icon Document.

        @param username: username of the owner of the Document
        @type username: string
        @param file_object: file object pointing to the image file data. Note
            that this resource must be closed by the caller once the object
            lifecycle is over. Not doing so will cause the application running
            out of resources, leading to crashes. To retrieve the filename,
            the "name" attribute is read, this won't work for fdopened files.
        @type file_object: string
        @param title: comment title
        @type title: string
        @param keywords: space separated string containing keywords
        @type keywords: string
        @return: a new Document object
        @rtype: Document
        """
        self._validate_strings(username, title, description)
        self._validate_string_list(keywords)
        self._validate_file_object(file_object)
        doc = Document(self._repository_id, None, Document.ICON_TYPE_ID)
        doc[DocumentFactory.DOCUMENT_USERNAME_ID] = username
        doc[DocumentFactory.DOCUMENT_PAYLOAD_ID] = \
            (os.path.basename(file_object.name), file_object)
        doc[Document.DOCUMENT_TITLE_ID] = title
        doc[Document.DOCUMENT_DESCRIPTION_ID] = description
        doc[Document.DOCUMENT_KEYWORDS_ID] = keywords
        return doc

    def video(self, username, file_object, title, description, keywords):
        """
        Generate a new Icon Document.

        @param username: username of the owner of the Document
        @type username: string
        @param file_object: file object pointing to the image file data. Note
            that this resource must be closed by the caller once the object
            lifecycle is over. Not doing so will cause the application running
            out of resources, leading to crashes. To retrieve the filename,
            the "name" attribute is read, this won't work for fdopened files.
        @type file_object: string
        @param title: comment title
        @type title: string
        @param keywords: space separated string containing keywords
        @type keywords: string
        @return: a new Document object
        @rtype: Document
        """
        self._validate_strings(username, title, description)
        self._validate_string_list(keywords)
        self._validate_file_object(file_object)
        doc = Document(self._repository_id, None, Document.VIDEO_TYPE_ID)
        doc[DocumentFactory.DOCUMENT_USERNAME_ID] = username
        doc[DocumentFactory.DOCUMENT_PAYLOAD_ID] = \
            (os.path.basename(file_object.name), file_object)
        doc[Document.DOCUMENT_TITLE_ID] = title
        doc[Document.DOCUMENT_DESCRIPTION_ID] = description
        doc[Document.DOCUMENT_KEYWORDS_ID] = keywords
        return doc

    def file(self, username, file_object, title, description, keywords):
        """
        Generate a new File Document.

        @param username: username of the owner of the Document
        @type username: string
        @param file_object: file object pointing to the image file data. Note
            that this resource must be closed by the caller once the object
            lifecycle is over. Not doing so will cause the application running
            out of resources, leading to crashes. To retrieve the filename,
            the "name" attribute is read, this won't work for fdopened files.
        @type file_object: string
        @param title: comment title
        @type title: string
        @param keywords: space separated string containing keywords
        @type keywords: string
        @return: a new Document object
        @rtype: Document
        """
        self._validate_strings(username, title, description)
        self._validate_string_list(keywords)
        self._validate_file_object(file_object)
        doc = Document(self._repository_id, None, Document.FILE_TYPE_ID)
        doc[DocumentFactory.DOCUMENT_USERNAME_ID] = username
        doc[DocumentFactory.DOCUMENT_PAYLOAD_ID] = \
            (os.path.basename(file_object.name), file_object)
        doc[Document.DOCUMENT_TITLE_ID] = title
        doc[Document.DOCUMENT_DESCRIPTION_ID] = description
        doc[Document.DOCUMENT_KEYWORDS_ID] = keywords
        return doc


class ClientWebServiceFactory(WebServiceFactory):
    """
    Main Entropy Client Repository Web Service Factory. Generates
    WebService objects that can be used to communicate with the established
    web service.
    """

    def __init__(self, entropy_client):
        """
        Overridden constructor.
        """
        WebServiceFactory.__init__(self, ClientWebService, entropy_client)


class ClientWebService(WebService):

    # Package maximum and minimum vote boundaries
    MAX_VOTE = 5.0
    MIN_VOTE = 0.0
    VALID_VOTES = (1, 2, 3, 4, 5)

    def __init__(self, entropy_client, repository_id):
        """
        ClientWebService constructor.
        """
        WebService.__init__(self, entropy_client, repository_id)
        self._live_cache = {}

    def _clear_live_cache(self, cache_key):
        try:
            self._live_cache.pop(cache_key)
        except KeyError:
            return

    def _clear_live_cache_startswith(self, cache_key_sw):
        for key in list(self._live_cache.keys()):
            if key.startswith(cache_key_sw):
                try:
                    self._live_cache.pop(key)
                except KeyError:
                    pass

    class DocumentError(WebService.WebServiceException):
        """
        Generic Document error object. Raised when Document object is
        invalid.
        """

    def document_factory(self):
        """
        Return a new DocumentFactory object, used to create new Document
        objects.

        @return: a DocumentFactory object
        @rtype: DocumentFactory
        """
        return DocumentFactory(self._repository_id)

    def get_votes(self, package_names, cache = True, cached = False):
        """
        For given package names, return the current vote. For missing votes
        or invalid package_name, None is assigned.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: mapping composed by package name as key and value as vote
            (float)
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        packages_str = " ".join(package_names)
        params = {
            "package_names": packages_str
        }
        hash_obj = hashlib.sha1()
        hash_obj.update(const_convert_to_rawstring(packages_str))
        hash_str = hash_obj.hexdigest()
        lcache_key = "get_votes_" + hash_str
        if cache:
            live_cached = self._live_cache.get(lcache_key)
            if live_cached is not None:
                return live_cached
        else:
            self._clear_live_cache(lcache_key)
        outcome = self._method_getter("get_votes", params, cache = cache,
            cached = cached, require_credentials = False)
        self._live_cache[lcache_key] = outcome
        return outcome

    def get_available_votes(self, cache = True, cached = False):
        """
        Return all the available votes for all the available packages.

        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: mapping composed by package name as key and value as vote
            (float)
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        if cache:
            live_cached = self._live_cache.get("get_available_votes")
            if live_cached is not None:
                return live_cached
        else:
            self._clear_live_cache("get_available_votes")
        # WARNING PLEASE don't change parameters that could affect the cache
        # without changing _update_get_available_votes_cache
        outcome = self._method_getter("get_available_votes", {}, cache = cache,
            cached = cached, require_credentials = False)
        self._live_cache["get_available_votes"] = outcome
        return outcome

    def get_downloads(self, package_names, cache = True, cached = False):
        """
        For given package names, return the current download counter.
        Packages having no download info will get None instead of int.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: mapping composed by package name as key and downloads as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        packages_str = " ".join(package_names)
        hash_obj = hashlib.sha1()
        hash_obj.update(const_convert_to_rawstring(packages_str))
        hash_str = hash_obj.hexdigest()
        lcache_key = "get_downloads_" + hash_str
        if cache:
            live_cached = self._live_cache.get(lcache_key)
            if live_cached is not None:
                return live_cached
        else:
            self._clear_live_cache(lcache_key)

        params = {
            "package_names": packages_str,
        }
        outcome = self._method_getter("get_downloads", params, cache = cache,
            cached = cached, require_credentials = False)
        self._live_cache[lcache_key] = outcome
        return outcome

    def get_available_downloads(self, cache = True, cached = False):
        """
        Return all the available downloads for all the available packages.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: mapping composed by package name as key and downloads as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        if cache:
            live_cached = self._live_cache.get("get_available_downloads")
            if live_cached is not None:
                return live_cached
        else:
            self._clear_live_cache("get_available_downloads")
        outcome = self._method_getter("get_available_downloads", {},
            cache = cache, cached = cached, require_credentials = False)
        self._live_cache["get_available_downloads"] = outcome
        return outcome

    def add_vote(self, package_name, vote, clear_available_cache = False):
        """
        For given package name, add a vote.

        @param package_name: package name, either atom or key
        @type package_name: string
        @keyword clear_available_cache: if True, even the
            "get_available_votes" on-disk cache gets cleared. Usually,
            this is not a very good thing (even if the cache contains outdated
            information) given the nature of the whole vote info.
            This is usually a push-only information.
            Please note that the "get_votes" cache is always cleared.
        @type clear_available_cache: bool
        @return: True, if vote was recorded, False otherwise
        @rtype: bool

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.RequestError: if vote is invalid.
        @raise WebService.AuthenticationRequired: if login information are
            not available (user interface should raise a login form, validate
            the credentials and retry the function call here)
        """
        valid = vote in ClientWebService.VALID_VOTES
        if not valid:
            raise WebService.RequestError("invalid vote", method = "add_vote")
        params = {
            "package_name": package_name,
            "vote": vote,
        }
        valid = self._method_getter("add_vote", params, cache = False,
            require_credentials = True)
        if valid:
            # NOTE: we can accept to be non-atomic in this case.
            # TODO: cannot remove all the vote cache when just one element gets
            # tained
            self._drop_cached("get_votes")
            self._clear_live_cache_startswith("get_votes_")
            # do not clear get_available_votes cache explicitly
            if clear_available_cache:
                self._drop_cached("get_available_votes")
                self._clear_live_cache("get_available_votes")
            else:
                # try to update get_available_votes cache
                self._update_get_available_votes_cache(package_name, vote)
        return valid

    def _update_get_available_votes_cache(self, package_name, vote):
        """
        Update get_available_votes cache adding package vote just submitted.
        If the get_available_votes cache exists.
        """
        try:
            avail_votes = self.get_available_votes(cache = True, cached = True)
        except WebService.CacheMiss:
            # bye!
            return
        cur_vote = avail_votes.get(package_name)
        if cur_vote is None:
            cur_vote = vote
        else:
            # just do the mean, even if it's untrue
            cur_vote = (cur_vote + vote) / 2
        avail_votes[package_name] = cur_vote
        # hope this will remain the same !
        cache_key = self._get_cache_key("get_available_votes", {})
        self._set_cached(cache_key, avail_votes)
        # clean up live cache, not really needed but just to make sure
        self._clear_live_cache("get_available_votes")

    def add_downloads(self, package_names, clear_available_cache = False):
        """
        Notify that a list of packages have been downloaded successfully.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @keyword clear_available_cache: if True, even the
            "get_available_downloads" on-disk cache gets cleared. Usually,
            this is not a very good thing (even if the cache contains outdated
            information) given the nature of the whole downloads info.
            This is usually a push-only information.
            Please note that the "get_downloads" cache is always cleared.
        @type clear_available_cache: bool
        @return: True, if download information was recorded, False otherwise
        @rtype: bool

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.AuthenticationRequired: if login information are
            not available (user interface should raise a login form, validate
            the credentials and retry the function call here)
        """
        enc = etpConst['conf_encoding']
        try:
            with codecs.open(etpConst['systemreleasefile'], "r", encoding=enc) \
                    as rel_f:
                release_string = rel_f.readline().strip()
        except (IOError, OSError):
            release_string = const_convert_to_unicode('--N/A--')

        hw_hash = self._settings['hw_hash']
        if not hw_hash:
            hw_hash = ""

        params = {
            "package_names": " ".join(package_names),
            "branch": self._settings['repositories']['branch'],
            "release_string": release_string,
            "hw_hash": hw_hash,
        }
        valid = self._method_getter("add_downloads", params, cache = False,
            require_credentials = False)
        if valid:
            # NOTE: we can accept to be non-atomic in this case.
            self._drop_cached("get_downloads")
            # do not clear get_available_downloads cache explicitly
            if clear_available_cache:
                self._drop_cached("get_available_downloads")
                self._clear_live_cache("get_available_downloads")
        return valid

    def get_images(self, package_names, offset = 0, latest = False,
        cache = True, cached = False, service_cache = False):
        """
        For given package names, return the current Document image object
        DocumentList.
        Packages having no images will get empty DocumentList as value.

        Results are paged, if offset is 0, the first page is returned.
        For gathering information regarding pages (total documents,
        offset provided, etc), see DocumentList API.

        @param package_names: list of names of the packages to query,
            either atom or key
        @type package_names: list
        @keyword offset: specify the offset document from where to start
            for each package_name
        @type offset: int
        @keyword latest: get documents in inverse order, from latest to oldest
        @type latest: bool
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @keyword service_cache: explicitly allow service to use its cache to
            satisfy the request
        @type service_cache: bool
        @return: mapping composed by package name as key and DocumentList
            as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        document_type_filter = [Document.IMAGE_TYPE_ID]
        return self.get_documents(package_names,
            document_type_filter = document_type_filter,
            latest = latest,
            offset = offset, cache = cache, cached = cached,
            service_cache = service_cache)

    def get_icons(self, package_names, offset = 0, latest = False,
        cache = True, cached = False, service_cache = False):
        """
        For given package names, return the current Document icon object
        DocumentList.
        Packages having no icon will get empty DocumentList as value.

        Results are paged, if offset is 0, the first page is returned.
        For gathering information regarding pages (total documents,
        offset provided, etc), see DocumentList API.

        @param package_names: list of names of the packages to query,
            either atom or key
        @type package_names: list
        @keyword offset: specify the offset document from where to start
            for each package_name
        @type offset: int
        @keyword latest: get documents in inverse order, from latest to oldest
        @type latest: bool
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @keyword service_cache: explicitly allow service to use its cache to
            satisfy the request
        @type service_cache: bool
        @return: mapping composed by package name as key and DocumentList
            as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        document_type_filter = [Document.ICON_TYPE_ID]
        return self.get_documents(package_names,
            document_type_filter = document_type_filter,
            latest = latest,
            offset = offset, cache = cache, cached = cached,
            service_cache = service_cache)

    def get_comments(self, package_names, offset = 0, latest = False,
        cache = True, cached = False, service_cache = False):
        """
        For given package names, return the current Document Comment object
        DocumentList.
        Packages having no comments will get empty DocumentList as value.

        Results are paged, if offset is 0, the first page is returned.
        For gathering information regarding pages (total documents,
        offset provided, etc), see DocumentList API.

        @param package_names: list of names of the packages to query,
            either atom or key
        @type package_names: list
        @keyword offset: specify the offset document from where to start
            for each package_name
        @type offset: int
        @keyword latest: get documents in inverse order, from latest to oldest
        @type latest: bool
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @keyword service_cache: explicitly allow service to use its cache to
            satisfy the request
        @type service_cache: bool
        @return: mapping composed by package name as key and DocumentList
            as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        document_type_filter = [Document.COMMENT_TYPE_ID]
        return self.get_documents(package_names,
            document_type_filter = document_type_filter,
            offset = offset, cache = cache, cached = cached,
            latest = latest, service_cache = service_cache)

    def get_documents(self, package_names, document_type_filter = None,
        offset = 0, latest = False, cache = True, cached = False,
        service_cache = False):
        """
        For given package names, return the current Document object
        DocumentList.
        Packages having no documents will get empty DocumentList as value.

        Results are paged, if offset is 0, the first page is returned.
        For gathering information regarding pages (total documents,
        offset provided, etc), see DocumentList API.

        @param package_names: list of names of the packages to query,
            either atom or key
        @type package_names: list
        @keyword document_type_filter: list of document type identifiers (
            see Document class) that are required.
        @type document_type_filter: list
        @keyword offset: specify the offset document from where to start
            for each package_name
        @type offset: int
        @keyword latest: get documents in inverse order, from latest to oldest
        @type latest: bool
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @keyword service_cache: explicitly allow service to use its cache to
            satisfy the request
        @type service_cache: bool
        @return: mapping composed by package name as key and DocumentList as
            value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        if document_type_filter is None:
            document_type_filter = []
        latest_str = "0"
        if latest:
            latest_str = "1"
        params = {
            "package_names": " ".join(package_names),
            "filter": " ".join([str(x) for x in document_type_filter]),
            "offset": offset,
            "latest": latest_str,
            "rev": "1",
        }
        if service_cache:
            params["cache"] = "1"
        objs = self._method_getter("get_documents", params, cache = cache,
            cached = cached, require_credentials = False)
        data = {}
        for package_name in package_names:
            objs_map = objs.get(package_name)
            if not objs_map:
                data[package_name] = DocumentList(
                    package_name, False, offset)
                continue

            has_more, docs = objs_map.get('has_more', False), \
                objs_map['docs']

            m_objs = data.setdefault(package_name,
                DocumentList(package_name, has_more, offset))
            for obj in docs:
                d_obj = Document(self._repository_id,
                    obj[Document.DOCUMENT_DOCUMENT_ID],
                        obj[Document.DOCUMENT_DOCUMENT_TYPE_ID])
                d_obj.update(obj)
                m_objs.append(d_obj)
        return data

    def get_documents_by_id(self, document_ids, cache = True, cached = False):
        """
        For given Document object identifiers, return the respective Document
        object.
        Unavailable Document object identifiers will have None as dict value.

        @param document_ids: list of document identifiers (int)
            either atom or key
        @type document_ids: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: mapping composed by Document identifier as key and
            Document as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        params = {
            "document_ids": " ".join([str(x) for x in document_ids]),
        }
        objs = self._method_getter("get_documents_by_id", params, cache = cache,
            cached = cached, require_credentials = False)
        data = {}
        for document_id in document_ids:
            obj = objs.get(document_id)
            if obj is None:
                # maybe json limitation? WTF?
                obj = objs.get(str(document_id))
            if obj is not None:
                d_obj = Document(self._repository_id,
                    obj[Document.DOCUMENT_DOCUMENT_ID],
                    obj[Document.DOCUMENT_DOCUMENT_TYPE_ID])
                d_obj.update(obj)
                obj = d_obj
            data[document_id] = obj
        return data

    def _drop_document_cache(self):
        """
        Drop all on-disk cache items related to document cache.
        """
        self._drop_cached("get_documents")
        self._drop_cached("get_documents_by_id")
        self._drop_cached("get_comments")
        self._drop_cached("get_icons")

    def add_document(self, package_name, document):
        """
        Send a new Document object to the service.
        This method will return the newly created remote document object, or
        raise exceptions in case the operation failed.

        @param package_name: package name, either atom or key
        @type package_name: string
        @return: the newly created remote Document object
        @rtype: Document

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.AuthenticationRequired: if login information are
            not available (user interface should raise a login form, validate
            the credentials and retry the function call here)
        @raise ClientWebService.DocumentError: if document submitted is
            invalid (contains invalid fields)
        """
        if not isinstance(document, Document):
            raise AttributeError("only accepting Document objects")
        if document[Document.DOCUMENT_DOCUMENT_ID] is not None:
            raise WebService.UnsupportedParameters("document is not new")
        # This returns None if document is not accepted
        params = document.copy()
        params['package_name'] = package_name
        # video requires huge timeout
        timeout = None # default
        if document.is_video():
            timeout = 300.0
        remote_document = self._method_getter("add_document", params,
            cache = False, require_credentials = True,
            timeout = timeout)
        if remote_document is None:
            raise ClientWebService.DocumentError("Document not accepted")

        # generate Document
        doc = Document(self._repository_id,
            remote_document[Document.DOCUMENT_DOCUMENT_ID],
            remote_document[Document.DOCUMENT_DOCUMENT_TYPE_ID])
        doc.update(remote_document)

        # NOTE: we can accept to be non-atomic in this case.
        self._drop_document_cache()
        return doc

    def get_document_url(self, document, cache = True):
        """
        Download (to Document.local_document() path, if available) the document
        data pointed at Document.document_url(). Document data path is returned
        in case of success, but an exception is always raised in case of
        failure.

        @param document: the Document object
        @type document: Document
        @keyword cache: use on-disk cache
        @type cache: bool
        @return: document data file path
        @rtype: string

        @raise ClientWebService.DocumentError: if document url is not available
        """
        document_url = document.document_url()
        if document_url is None:
            raise ClientWebService.DocumentError("Document url not available")
        local_document = document.local_document()
        if local_document is None:
            # wtf!
            raise ClientWebService.DocumentError(
                "Document (local) not available")

        local_dir = os.path.dirname(local_document)
        if not os.path.isdir(local_dir):
            # try to make one
            try:
                os.makedirs(local_dir, 0o775)
                if etpConst['entropygid'] is not None:
                    const_setup_perms(local_dir, etpConst['entropygid'])
            except (OSError, IOError):
                raise ClientWebService.DocumentError(
                    "Insufficient privileges")
        elif not const_dir_writable(local_dir):
            raise ClientWebService.DocumentError(
                "Insufficient privileges (2)")

        if cache and (os.path.isfile(local_document)):
            # cached, just return
            return local_document

        fetch_errors = (
            UrlFetcher.TIMEOUT_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_WARN,
        )
        local_document_dir = os.path.dirname(local_document)
        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = const_mkstemp(
                dir=local_document_dir, prefix="get_document_url")

            fetcher = self._entropy._url_fetcher(
                document_url, tmp_path, resume = False)
            rc = fetcher.download()

            if rc in fetch_errors:
                raise ClientWebService.DocumentError(
                    "Document download failed: %s" % (rc,))

            os.rename(tmp_path, local_document)
            tmp_path = None

        finally:
            if tmp_fd is not None:
                os.close(tmp_fd)
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if not os.path.isfile(local_document):
            raise ClientWebService.DocumentError(
                "Document download failed")

        try:
            os.chmod(local_document, 0o664)
            if etpConst['entropygid'] is not None:
                os.chown(local_document, -1, etpConst['entropygid'])
        except OSError:
            raise ClientWebService.DocumentError(
                "Insufficient privileges (3)")

        del fetcher
        return local_document

    def remove_document(self, document_id):
        """
        Remove a Document (through its id) from the service repository.

        @param document_id: Entropy Document identifier
        @type document_id: int
        @return: True if document has been removed, False if Document doesn't
            exist
        @rtype: bool

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.AuthenticationRequired: if login information are
            not available (user interface should raise a login form, validate
            the credentials and retry the function call here)
        """
        params = {
            Document.DOCUMENT_DOCUMENT_ID: document_id,
        }
        result = self._method_getter("remove_document", params,
            cache = False, require_credentials = True)
        # NOTE: we can accept to be non-atomic in this case.
        self._drop_document_cache()
        return result

    def report_error(self, error_params):
        """
        Entropy Client Error reporting method. This is mainly used by
        Entropy internal code in order to submit a stacktrace and other data
        to Entropy developers. "error_params" consinsts in a dictionary
        containing error data in string format as values.

        @param error_params: dictionary containing error report data
        @type error_params: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occurred (error code passed as
            exception argument)
        @raise WebService.AuthenticationRequired: if require_credentials
            is True and credentials are required.
        @raise WebService.AuthenticationFailed: if credentials are
            not valid
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web
            Service API do not match
        @raise WebService.MethodResponseError; if method execution failed
        """
        params = {}
        file_params = {}
        for k, v in error_params.items():
            if isinstance(v, const_get_stringtype()):
                sio = StringIO()
                sio.write(v)
                sio.seek(0)
                file_params[k] = (k + ".txt", sio)
            else:
                params[k] = v
        self._method_getter("report_error", params,
            file_params = file_params, require_credentials = False,
            cache = False)


class RepositoryWebServiceFactory(WebServiceFactory):
    """
    Repository related Web Service Factory. Generates
    RepositoryWebService objects that can be used to obtain package metadata
    and general repository information.
    """

    def __init__(self, entropy_client):
        """
        Overridden constructor.
        """
        WebServiceFactory.__init__(self, RepositoryWebService, entropy_client)


class RepositoryWebService(WebService):

    # The maximum amount of packages whose metadata can be requested
    # at once by RepositoryWebService.get_packages_metadata()
    MAXIMUM_PACKAGE_REQUEST_SIZE = 10

    def update_service_available(self, cache = True, cached = False):
        """
        Return whether the Web Service is supporting repositories update
        through the WebService. In general, this is true if service_available()
        returns True, but the feature can be disabled client side through
        packages.db.webservices.

        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: True, if service is available
        @rtype: bool

        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occurred (error code passed as exception
            argument)
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        eapi = self._config['update_eapi']
        if eapi is not None:
            if eapi < 3:
                const_debug_write(
                    __name__,
                    "repository configuration blocks updates "
                    "through Entropy WebServices")
                return False
        return self.service_available(cache = cache, cached = cached)

    def service_available(self, cache = True, cached = False):
        """
        Return whether the Web Service is correctly able to answer our
        repository-based requests.

        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @keyword cached: if True, it will only use the on-disk cached call
            result and raise WebService.CacheMiss if not found.
        @type cached: bool
        @return: True, if service is available
        @rtype: bool

        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occurred (error code passed as exception
            argument)
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        @raise WebService.CacheMiss: if cached=True and cached object is not
            available
        """
        eapi = self._config['repo_eapi']
        if eapi is not None:
            if eapi < 3:
                const_debug_write(
                    __name__,
                    "repository configuration blocks Entropy WebServices")
                return False
        params = {
            'arch': etpConst['currentarch'],
            'product': self._settings['repositories']['product'],
            'branch': self._settings['repositories']['branch'],
        }
        return self._method_getter("repository_service_available", params,
            cache = cache, cached = cached, require_credentials = False)

    def get_revision(self):
        """
        Return the repository revision as it's advertised remotely.
        The revision is returned in string format.
        Please note that this method doesn't do any caching.

        @return: the repository revision
        @rtype: string

        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occurred (error code passed as exception
            argument)
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        """
        params = {
            'arch': etpConst['currentarch'],
            'product': self._settings['repositories']['product'],
            'branch': self._settings['repositories']['branch'],
        }
        return self._method_getter("repository_revision", params,
            cache = False, cached = False, require_credentials = False)

    def get_repository_metadata(self):
        """
        Return the repository metadata for the selected repository. It is
        usually an opaque object in dict form that contains all the metadata
        not related to single packages.
        As for API=1, the returned metadata is the following:
        "sets" => EntropyRepositoryBase.retrievePackageSets()
        "treeupdates_actions" => EntropyRepositoryBase.listAllTreeUpdatesActions()
        "treeupdates_digest" => EntropyRepositoryBase.retrieveRepositoryUpdatesDigest()
        "revision" => <the actual repository revision, string form>
        "checksum" => EntropyRepositoryBase.checksum(do_order = True,
                strict = False, include_signatures = True)
        Please note that this method doesn't do any caching.

        @return: the repository metadata
        @rtype: dict

        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occurred (error code passed as exception
            argument)
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        """
        params = {
            'arch': etpConst['currentarch'],
            'product': self._settings['repositories']['product'],
            'branch': self._settings['repositories']['branch'],
        }
        return self._method_getter("get_repository_metadata", params,
            cache = False, cached = False, require_credentials = False)

    def get_package_ids(self):
        """
        Return a list of available package identifiers in the selected
        repository.
        Please note that this method doesn't do any caching.

        @return: the repository metadata
        @rtype: dict

        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occurred (error code passed as exception
            argument)
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        """
        params = {
            'arch': etpConst['currentarch'],
            'product': self._settings['repositories']['product'],
            'branch': self._settings['repositories']['branch'],
        }
        return self._method_getter("get_package_ids", params,
            cache = False, cached = False, require_credentials = False)

    def get_packages_metadata(self, package_ids):
        """
        Return a list of available package identifiers in the selected
        repository.
        Please note that this method doesn't do any caching.
        Moreover, package_ids list cannot be longer than
        RepositoryWebService.MAXIMUM_PACKAGE_REQUEST_SIZE, this is checked
        both server-side, for your joy.
        Data is returned in dict form, key is package_id, value is package
        metadata, same you can get by calling:
        EntropyRepositoryBase.getPackageData(
            package_id, content_insert_formatted = True,
            get_content = False, get_changelog = False)

        @return: the repository metadata list
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not available
            remotely and an error occurred (error code passed as exception
            argument)
        @raise WebService.MalformedResponse: if JSON response cannot be
            converted back to dict.
        @raise WebService.UnsupportedAPILevel: if client API and Web Service
            API do not match
        @raise WebService.MethodResponseError; if method execution failed
        """
        try:
            package_ids_str = " ".join([str(int(x)) for x in \
                sorted(package_ids)])
        except ValueError:
            raise WebService.UnsupportedParameters("unsupported input params")
        params = {
            "package_ids": package_ids_str,
            'arch': etpConst['currentarch'],
            'product': self._settings['repositories']['product'],
            'branch': self._settings['repositories']['branch'],
        }
        pkg_meta = self._method_getter("get_packages_metadata", params,
            cache = False, cached = False, require_credentials = False)
        return dict((int(x), y) for x, y in pkg_meta.items())
