# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Client Repository Web Services Client interface}.

"""
__all__ = ["ClientWebServiceFactory", "ClientWebService", "Document",
    "DocumentFactory"]

import os
import time
from entropy.const import const_get_stringtype
from entropy.i18n import _
from entropy.services.client import WebServiceFactory, WebService

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
        if self.get(DocumentFactory.DOCUMENT_TITLE_ID) == \
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


class DocumentFactory(object):
    """
    Class to generate valid, new Document objects.
    """

    # Document hash table key for the document title
    DOCUMENT_TITLE_ID = "title"

    # Document hash table key for the document username
    DOCUMENT_USERNAME_ID = "username"

    # Document hash table key for the document description
    DOCUMENT_DESCRIPTION_ID = "description"

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
        doc[DocumentFactory.DOCUMENT_TITLE_ID] = title
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
        doc[DocumentFactory.DOCUMENT_TITLE_ID] = title
        doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID] = description
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
        doc[DocumentFactory.DOCUMENT_TITLE_ID] = title
        doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID] = description
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
        doc[DocumentFactory.DOCUMENT_TITLE_ID] = title
        doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID] = description
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
        doc[DocumentFactory.DOCUMENT_TITLE_ID] = title
        doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID] = description
        doc[Document.DOCUMENT_KEYWORDS_ID] = keywords
        return doc


class ClientWebServiceFactory(WebServiceFactory):
    """
    Main Entropy Client Repository Web Service Factory. Generates
    WebService objects that can be used to communicate with the established
    web service.
    This class should be instantiated by calling 
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

    def get_votes(self, package_names, cache = True):
        """
        For given package names, return the current vote. For missing votes
        or invalid package_name, None is assigned.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @return: mapping composed by package name as key and value as vote
            (float)
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        params = {
            "package_names": " ".join(package_names)
        }
        return self._method_getter("get_votes", params, cache = cache,
            require_credentials = False)

    def get_downloads(self, package_names, cache = True):
        """
        For given package names, return the current download counter.
        Packages having no download info will get None instead of int.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @return: mapping composed by package name as key and downloads as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        params = {
            "package_names": " ".join(package_names)
        }
        return self._method_getter("get_downloads", params, cache = cache,
            require_credentials = False)

    def add_vote(self, package_name, vote):
        """
        For given package name, add a vote.

        @param package_name: package name, either atom or key
        @type package_name: string
        @return: True, if vote was recorded, False otherwise
        @rtype: bool

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        return valid

    def add_downloads(self, package_names):
        """
        Notify that a list of packages have been downloaded successfully.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @return: True, if download information was recorded, False otherwise
        @rtype: bool

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
            "package_names": " ".join(package_names),
        }
        valid = self._method_getter("add_downloads", params, cache = False,
            require_credentials = True)
        if valid:
            # NOTE: we can accept to be non-atomic in this case.
            # TODO: cannot remove all the vote cache when just one element gets
            # tained
            self._drop_cached("get_downloads")
        return valid

    def get_icons(self, package_names, cache = True):
        """
        For given package names, return the current Document icon object list.
        Packages having no icon will get empty list as value.

        @param package_names: list of names of the packages to query,
            either atom or key
        @type package_names: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @return: mapping composed by package name as key and Document list
            as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        document_type_filter = [Document.IMAGE_TYPE_ID]
        data = self.get_documents(package_names,
            document_type_filter = document_type_filter, cache = cache)
        icons_data = {}
        for key in list(data.keys()):
            icons_data[key] = [x for x in data.get(key, []) if x.is_icon()]
        return icons_data

    def get_comments(self, package_names, cache = True):
        """
        For given package names, return the current Document Comment object
        list.
        Packages having no comments will get empty list as value.

        @param package_names: list of names of the packages to query,
            either atom or key
        @type package_names: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @return: mapping composed by package name as key and Document list
            as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        document_type_filter = [Document.COMMENT_TYPE_ID]
        data = self.get_documents(package_names,
            document_type_filter = document_type_filter, cache = cache)
        icons_data = {}
        for key in list(data.keys()):
            icons_data[key] = [x for x in data.get(key, []) if x.is_icon()]
        return icons_data

    def get_documents(self, package_names, document_type_filter = None,
        cache = True):
        """
        For given package names, return the current Document object list.
        Packages having no documents will get empty list as value.

        @param package_names: list of names of the packages to query,
            either atom or key
        @type package_names: list
        @keyword document_type_filter: list of document type identifiers (
            see Document class) that are required.
        @type document_type_filter: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @return: mapping composed by package name as key and Document list as
            value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        if document_type_filter is None:
            document_type_filter = []
        params = {
            "package_names": " ".join(package_names),
            "filter": " ".join([str(x) for x in document_type_filter]),
        }
        objs = self._method_getter("get_documents", params, cache = cache,
            require_credentials = False)
        data = {}
        for package_name in package_names:
            obj = objs.get(package_name)
            if obj is not None:
                d_obj = Document(self._repository_id, obj['document_id'],
                    obj['document_type_id'])
                d_obj.update(obj)
                obj = d_obj
            data[package_name] = obj
        return data

    def get_documents_by_id(self, document_ids, cache = True):
        """
        For given Document object identifiers, return the respective Document
        object.
        Unavailable Document object identifiers will have None as dict value.

        @param document_ids: list of document identifiers (int)
            either atom or key
        @type document_ids: list
        @keyword cache: True means use on-disk cache if available?
        @type cache: bool
        @return: mapping composed by Document identifier as key and
            Document as value
        @rtype: dict

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        params = {
            "document_ids": " ".join([str(x) for x in document_ids]),
        }
        objs = self._method_getter("get_documents_by_id", params, cache = cache,
            require_credentials = False)
        data = {}
        for document_id in document_ids:
            obj = objs.get(document_id)
            if obj is not None:
                d_obj = Document(self._repository_id, obj['document_id'],
                    obj['document_type_id'])
                d_obj.update(obj)
                obj = d_obj
            data[package_name] = obj
        return data

    def _drop_document_cache(self):
        """
        Drop all on-disk cache items related to document cache.
        """
        self._drop_cached("get_documents")
        self._drop_cached("get_documents_by_id")
        self._drop_cached("get_comments")
        self._drop_cached("get_icons")

    def add_document(self, document):
        """
        Send a new Document object to the service.
        This method will return the newly created remote document object, or
        raise exceptions in case the operation failed.

        @param package_names: list of package names, either atoms or keys
        @type package_names: list
        @return: the newly created remote Document object
        @rtype: Document

        @raise WebService.UnsupportedParameters: if input parameters are
            invalid
        @raise WebService.RequestError: if request cannot be satisfied
        @raise WebService.MethodNotAvailable: if API method is not
            available remotely and an error occured (error code passed as
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
        if document['document_id'] is not None:
            raise WebService.UnsupportedParameters("document is not new")
        # This returns None if document is not accepted
        remote_document = self._method_getter("add_document", document,
            cache = False, require_credentials = True)
        if remote_document is None:
            raise ClientWebService.DocumentError("Document not accepted")

        # NOTE: we can accept to be non-atomic in this case.
        self._drop_document_cache()
        return remote_document

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
            available remotely and an error occured (error code passed as
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
            available remotely and an error occured (error code passed as
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
        self._method_getter("report_error", error_params,
            require_credentials = False, cache = False)
