# -*- coding: utf-8 -*-
import sys
import os
import tempfile
import unittest
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from entropy.client.interfaces import Client
from entropy.services.client import WebService
from entropy.client.services.interfaces import Document, DocumentFactory, \
    DocumentList, ClientWebService
from entropy.const import etpConst, etpUi, const_convert_to_rawstring, \
    const_convert_to_unicode, const_get_stringtype
import entropy.tools
import tests._misc as _misc
from entropy.core.settings.base import SystemSettings


class EntropyWebServicesTest(unittest.TestCase):

    def __init__(self, *args):
        unittest.TestCase.__init__(self, *args)
        self._repository_id = \
            SystemSettings()['repositories']['default_repository']

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()
        self._entropy = Client(installed_repo = -1, indexing = False,
            xcache = False, repo_validation = False)
        self._factory = self._entropy.WebServices()
        self._fake_user = "entropy_unittest"
        self._fake_pass = "entropy_unittest"
        self._fake_unicode_user = const_convert_to_unicode("entropy_unittèst2",
            enctype = "utf-8")
        self._fake_unicode_pass = const_convert_to_unicode("entropy_unittèst",
            enctype = "utf-8")
        self._fake_package_name = "app-something/entropy-unittest"
        self._fake_package_name_utf8 = const_convert_to_unicode(
            "app-something/entropy-unìttest")
        self._real_package_name = "media-sound/amarok"

    def tearDown(self):
        """
        tearDown is run after each test
        """
        sys.stdout.write("%s ran\n" % (self,))
        sys.stdout.flush()
        # calling destroy() and shutdown()
        # need to call destroy() directly to remove all the SystemSettings
        # plugins because shutdown() doesn't, since it's meant to be called
        # right before terminating the process
        self._entropy.destroy()
        self._entropy.shutdown()

    def test_credentials(self):
        webserv = self._factory.new(self._repository_id)
        webserv.add_credentials("lxnay", "test")
        self.assertEqual(webserv.get_credentials(), "lxnay")
        self.assertEqual(webserv.credentials_available(), True)
        self.assert_(webserv.remove_credentials())
        self.assertEqual(webserv.credentials_available(), False)

    def test_credentials_utf8(self):
        user = const_convert_to_unicode("lxnày")
        password = const_convert_to_unicode("pààààss")
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        webserv.add_credentials(user, password)
        self.assertEqual(webserv.get_credentials(), user)
        self.assertEqual(webserv.credentials_available(), True)
        self.assert_(webserv.remove_credentials())
        self.assertEqual(webserv.credentials_available(), False)

    def test_validate_credentials(self):
        webserv = self._factory.new(self._repository_id)
        webserv.remove_credentials()
        webserv.add_credentials(self._fake_user, self._fake_pass)
        try:
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
        finally:
            webserv.remove_credentials()

    def test_validate_credentials_error(self):
        webserv = self._factory.new(self._repository_id)
        webserv.remove_credentials()
        user = const_convert_to_unicode("lxnay")
        password = const_convert_to_unicode("paasssdsss")
        webserv.add_credentials(user, password)
        try:
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), user)
            # credentials must be INVALID
            self.assertRaises(WebService.AuthenticationFailed,
                webserv.validate_credentials)
        finally:
            webserv.remove_credentials()

    def test_validate_credentials_utf8(self):
        webserv = self._factory.new(self._repository_id)
        webserv.remove_credentials()
        webserv.add_credentials(self._fake_unicode_user,
            self._fake_unicode_pass)
        try:
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_unicode_user)
            # credentials must be valid
            webserv.validate_credentials()
        finally:
            webserv.remove_credentials()

    def test_query_utf8(self):
        webserv = self._factory.new(self._repository_id)
        # this must raise WebService.MethodResponseError
        self.assertRaises(WebService.MethodResponseError,
            webserv.get_votes, (self._fake_package_name_utf8,))

    def test_get_votes(self):
        webserv = self._factory.new(self._repository_id)
        # this must return valid data
        vote_data = webserv.get_votes([self._fake_package_name], cache = False)
        self.assert_(isinstance(vote_data, dict))
        self.assert_(self._fake_package_name in vote_data)
        if vote_data[self._fake_package_name] is not None:
            self.assert_(isinstance(vote_data[self._fake_package_name], float))
        else:
            self.assert_(vote_data[self._fake_package_name] is None)

    def test_get_available_votes(self):
        webserv = self._factory.new(self._repository_id)
        # this must return valid data
        vote_data = webserv.get_available_votes(cache = False)
        self.assert_(isinstance(vote_data, dict))
        self.assert_(self._real_package_name in vote_data)
        self.assert_(isinstance(vote_data[self._real_package_name], float))
        for key, val in vote_data.items():
            self.assert_(entropy.tools.validate_package_name(key))
            self.assert_(isinstance(val, float))
            self.assert_(int(val) in ClientWebService.VALID_VOTES)

    def test_get_votes_cannot_exists(self):
        webserv = self._factory.new(self._repository_id)
        key = "app-doesntexistforsure/asdweasfoo"
        # this must return valid data
        vote_data = webserv.get_votes([key], cache = False)
        self.assert_(isinstance(vote_data, dict))
        self.assert_(key in vote_data)
        self.assert_(vote_data[key] is None)

    def test_add_vote(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        # try with success
        webserv.remove_credentials()
        try:
            webserv.add_vote(self._fake_package_name, 4)
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            webserv.add_vote(self._fake_package_name, 4)
        finally:
            webserv.remove_credentials()

        # now check back if average vote is still 4.0
        vote = webserv.get_votes(
            [self._fake_package_name])[self._fake_package_name]
        self.assertEqual(vote, 4.0)

    def test_add_vote_failure(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        # try with success
        webserv.remove_credentials()
        invalid_package_name = self._fake_package_name + "'''"
        try:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            webserv.add_vote(invalid_package_name, 4)
            self.assert_(False)
        except webserv.MethodResponseError:
            self.assert_(True) # valid
        finally:
            webserv.remove_credentials()

        # now check back if average vote is still 4.0
        try:
            vote = webserv.get_votes(
                [invalid_package_name])[invalid_package_name]
            self.assert_(False)
        except webserv.MethodResponseError:
            self.assert_(True) # valid

    def test_get_available_downloads(self):
        webserv = self._factory.new(self._repository_id)
        # this must return valid data
        down_data = webserv.get_available_downloads(cache = False)
        self.assert_(isinstance(down_data, dict))
        self.assert_(self._real_package_name in down_data)
        self.assert_(isinstance(down_data[self._real_package_name], int))
        for key, val in down_data.items():
            self.assert_(entropy.tools.validate_package_name(key))
            self.assert_(isinstance(val, int))
            self.assert_(val >= 0)

    def test_add_downloads(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        pk = self._fake_package_name
        pkg_list = [pk]
        cur_downloads = webserv.get_downloads(pkg_list, cache = False)[pk]
        if cur_downloads is None:
            cur_downloads = 0

        # can be False if the test is run repeatedly, due to the anti-flood
        # protection
        added = webserv.add_downloads([self._fake_package_name])
        self.assert_(isinstance(added, bool))

        # expect (cur_downloads + 1) now, use cache, so to check if cache
        # is cleared correctly
        expected_downloads = cur_downloads
        if added:
            expected_downloads += 1
        new_downloads = webserv.get_downloads(pkg_list)[pk]
        self.assertEqual(expected_downloads, new_downloads)

    def test_add_icon(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        description = const_convert_to_unicode("descrìption")
        title = const_convert_to_unicode("tìtle")

        tmp_fd, tmp_path = tempfile.mkstemp()
        with open(tmp_path, "ab+") as tmp_f:
            tmp_f.write(const_convert_to_rawstring('\x89PNG\x00\x00'))
            tmp_f.flush()
            tmp_f.seek(0)
            doc = doc_factory.icon(self._fake_user, tmp_f, title,
                description, keywords)
            webserv.remove_credentials()
            try:
                webserv.add_document(self._fake_package_name, doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(self._fake_package_name, doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id],
            cache = False)[doc_id]
        self.assert_(new_doc.is_icon())
        self.assert_(remote_doc.is_icon())
        self.assert_(not remote_doc.is_comment())
        self.assert_(not remote_doc.is_image())
        self.assert_(not remote_doc.is_video())
        self.assert_(not remote_doc.is_file())
        self.assertEqual(new_doc.repository_id(), self._repository_id)
        self.assertEqual(new_doc.document_type(), remote_doc.document_type())
        self.assertEqual(new_doc.document_id(), remote_doc.document_id())
        self.assertEqual(new_doc.repository_id(), remote_doc.repository_id())
        self.assertEqual(new_doc.document_keywords(), keywords)

        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_USERNAME_ID],
            remote_doc[DocumentFactory.DOCUMENT_USERNAME_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DOCUMENT_ID],
            remote_doc[Document.DOCUMENT_DOCUMENT_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DESCRIPTION_ID],
            remote_doc[Document.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[Document.DOCUMENT_TITLE_ID],
            remote_doc[Document.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        webserv.remove_credentials()
        try:
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID])
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            self.assert_(
                webserv.remove_document(
                    remote_doc[Document.DOCUMENT_DOCUMENT_ID]))
            # got the new document back, which is the same plus document_id
        finally:
            webserv.remove_credentials()

    def test_add_icon_fail(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        description = const_convert_to_unicode("descrìption")
        title = const_convert_to_unicode("tìtle")

        tmp_fd, tmp_path = tempfile.mkstemp()
        with open(tmp_path, "ab+") as tmp_f:
            img_dump = '\x89\xFF\x00\x00\x89\xFF\x89\xFF\x89\xFF'
            tmp_f.write(const_convert_to_rawstring(img_dump))
            tmp_f.flush()
            tmp_f.seek(0)
            doc = doc_factory.icon(self._fake_user, tmp_f, title,
                description, keywords)
            webserv.remove_credentials()
            try:
                webserv.add_document(self._fake_package_name, doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                self.assertRaises(WebService.MethodResponseError,
                    webserv.add_document, self._fake_package_name, doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

    def test_add_image_fail(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        description = const_convert_to_unicode("descrìption")
        title = const_convert_to_unicode("tìtle")

        tmp_fd, tmp_path = tempfile.mkstemp()
        with open(tmp_path, "ab+") as tmp_f:
            img_dump = '\x89\xFF\x00\x00\x89\xFF\x89\xFF\x89\xFF'
            tmp_f.write(const_convert_to_rawstring(img_dump))
            tmp_f.flush()
            tmp_f.seek(0)
            doc = doc_factory.image(self._fake_user, tmp_f, title,
                description, keywords)
            webserv.remove_credentials()
            try:
                webserv.add_document(self._fake_package_name, doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                self.assertRaises(WebService.MethodResponseError,
                    webserv.add_document, self._fake_package_name, doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

    def test_add_image(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        description = const_convert_to_unicode("descrìption")
        title = const_convert_to_unicode("tìtle")

        tmp_fd, tmp_path = tempfile.mkstemp()
        with open(tmp_path, "ab+") as tmp_f:
            tmp_f.write(const_convert_to_rawstring('\x89PNG\x00\x00'))
            tmp_f.flush()
            tmp_f.seek(0)
            doc = doc_factory.image(self._fake_user, tmp_f, title,
                description, keywords)
            webserv.remove_credentials()
            try:
                webserv.add_document(self._fake_package_name, doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(self._fake_package_name, doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id],
            cache = False)[doc_id]
        self.assert_(new_doc.is_image())
        self.assert_(remote_doc.is_image())
        self.assert_(not remote_doc.is_comment())
        self.assert_(not remote_doc.is_icon())
        self.assert_(not remote_doc.is_video())
        self.assert_(not remote_doc.is_file())
        self.assertEqual(new_doc.document_type(), remote_doc.document_type())
        self.assertEqual(new_doc.document_id(), remote_doc.document_id())
        self.assertEqual(new_doc.repository_id(), self._repository_id)
        self.assertEqual(new_doc.repository_id(), remote_doc.repository_id())
        self.assertEqual(new_doc.document_keywords(), keywords)

        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_USERNAME_ID],
            remote_doc[DocumentFactory.DOCUMENT_USERNAME_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DOCUMENT_ID],
            remote_doc[Document.DOCUMENT_DOCUMENT_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DESCRIPTION_ID],
            remote_doc[Document.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[Document.DOCUMENT_TITLE_ID],
            remote_doc[Document.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        webserv.remove_credentials()
        try:
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID])
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            self.assert_(
                webserv.remove_document(
                    remote_doc[Document.DOCUMENT_DOCUMENT_ID]))
            # got the new document back, which is the same plus document_id
        finally:
            webserv.remove_credentials()

    def test_add_comment(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        comment = const_convert_to_unicode("comment hellò")
        title = const_convert_to_unicode("tìtle")

        doc = doc_factory.comment(self._fake_user, comment, title, keywords)
        webserv.remove_credentials()
        try:
            webserv.add_document(self._fake_package_name, doc)
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            new_doc = webserv.add_document(self._fake_package_name, doc)
            self.assert_(new_doc is not None)
            # got the new document back, which is the same plus document_id
        finally:
            webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id],
            cache = False)[doc_id]
        self.assert_(remote_doc is not None)
        self.assert_(new_doc.is_comment())
        self.assert_(remote_doc.is_comment())
        self.assert_(not remote_doc.is_image())
        self.assert_(not remote_doc.is_icon())
        self.assert_(not remote_doc.is_video())
        self.assert_(not remote_doc.is_file())
        self.assertEqual(new_doc.repository_id(), self._repository_id)
        self.assertEqual(new_doc.document_type(), remote_doc.document_type())
        self.assertEqual(new_doc.document_id(), remote_doc.document_id())
        self.assertEqual(new_doc.repository_id(), remote_doc.repository_id())
        self.assertEqual(new_doc.document_keywords(), keywords)

        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_USERNAME_ID],
            remote_doc[DocumentFactory.DOCUMENT_USERNAME_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DOCUMENT_ID],
            remote_doc[Document.DOCUMENT_DOCUMENT_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_DATA_ID], comment)
        self.assertEqual(new_doc[Document.DOCUMENT_TITLE_ID],
            remote_doc[Document.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        webserv.remove_credentials()
        try:
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID])
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            self.assert_(
                webserv.remove_document(
                    remote_doc[Document.DOCUMENT_DOCUMENT_ID]))
            # got the new document back, which is the same plus document_id
        finally:
            webserv.remove_credentials()

    def test_add_file(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available())
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        description = const_convert_to_unicode("descrìption")
        title = const_convert_to_unicode("tìtle")

        tmp_fd, tmp_path = tempfile.mkstemp()
        with open(tmp_path, "ab+") as tmp_f:
            tmp_f.write(const_convert_to_rawstring('BZ2\x00\x00'))
            tmp_f.flush()
            tmp_f.seek(0)
            doc = doc_factory.file(self._fake_user, tmp_f, title,
                description, keywords)
            webserv.remove_credentials()
            try:
                webserv.add_document(self._fake_package_name, doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(self._fake_package_name, doc)
                self.assert_(new_doc is not None)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id],
            cache = False)[doc_id]
        self.assert_(new_doc.is_file())
        self.assert_(remote_doc.is_file())
        self.assert_(not remote_doc.is_comment())
        self.assert_(not remote_doc.is_icon())
        self.assert_(not remote_doc.is_video())
        self.assert_(not remote_doc.is_image())
        self.assertEqual(new_doc.document_type(), remote_doc.document_type())
        self.assertEqual(new_doc.document_id(), remote_doc.document_id())
        self.assertEqual(new_doc.repository_id(), self._repository_id)
        self.assertEqual(new_doc.repository_id(), remote_doc.repository_id())
        self.assertEqual(new_doc.document_keywords(), keywords)

        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_USERNAME_ID],
            remote_doc[DocumentFactory.DOCUMENT_USERNAME_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DOCUMENT_ID],
            remote_doc[Document.DOCUMENT_DOCUMENT_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DESCRIPTION_ID],
            remote_doc[Document.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[Document.DOCUMENT_TITLE_ID],
            remote_doc[Document.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        webserv.remove_credentials()
        try:
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID])
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            self.assert_(
                webserv.remove_document(
                    remote_doc[Document.DOCUMENT_DOCUMENT_ID]))
            # got the new document back, which is the same plus document_id
        finally:
            webserv.remove_credentials()

    def test_add_video(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available())
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        description = const_convert_to_unicode("descrìption")
        title = const_convert_to_unicode("tìtle")

        test_video_file = _misc.get_test_video_file()
        with open(test_video_file, "rb") as tmp_f:
            doc = doc_factory.video(self._fake_user, tmp_f, title,
                description, keywords)
            # do not actually publish the video
            doc['pretend'] = 1
            webserv.remove_credentials()
            try:
                webserv.add_document(self._fake_package_name, doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(self._fake_package_name, doc)
                self.assert_(new_doc is not None)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id],
            cache = False)[doc_id]
        self.assert_(new_doc.is_video())
        self.assert_(remote_doc.is_video())
        self.assert_(not remote_doc.is_comment())
        self.assert_(not remote_doc.is_icon())
        self.assert_(not remote_doc.is_file())
        self.assert_(not remote_doc.is_image())
        self.assertEqual(new_doc.document_type(), remote_doc.document_type())
        self.assertEqual(new_doc.document_id(), remote_doc.document_id())
        self.assertEqual(new_doc.repository_id(), self._repository_id)
        self.assertEqual(new_doc.repository_id(), remote_doc.repository_id())
        self.assertEqual(new_doc.document_keywords(), keywords)

        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_USERNAME_ID],
            remote_doc[DocumentFactory.DOCUMENT_USERNAME_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DOCUMENT_ID],
            remote_doc[Document.DOCUMENT_DOCUMENT_ID])
        self.assertEqual(new_doc[Document.DOCUMENT_DESCRIPTION_ID],
            remote_doc[Document.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[Document.DOCUMENT_TITLE_ID],
            remote_doc[Document.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[Document.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        webserv.remove_credentials()
        try:
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID])
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            self.assert_(
                webserv.remove_document(
                    remote_doc[Document.DOCUMENT_DOCUMENT_ID]))
            # got the new document back, which is the same plus document_id
        finally:
            webserv.remove_credentials()

    def test_get_documents(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        pk = self._real_package_name
        return self._test_get_documents(pk, webserv.get_documents)

    def test_get_documents_comments(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        pk = self._real_package_name
        return self._test_get_documents(pk, webserv.get_comments)

    def test_get_documents_icons(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        pk = self._real_package_name
        return self._test_get_documents(pk, webserv.get_icons)

    def _test_get_documents(self, pk, webserv_func):
        docs = webserv_func([pk], cache = False)
        self.assert_(pk in docs)
        self.assert_(isinstance(docs[pk], DocumentList))
        for vals in docs.values():
            self.assert_(isinstance(vals, DocumentList))
            self.assertEqual(vals.package_name(), pk)
            self.assert_(isinstance(vals.total(), int))
            self.assert_(isinstance(vals.has_more(), int))
            self.assertEqual(vals.offset(), 0)
            for val in vals:
                self.assert_(isinstance(val, Document))
                self.assertEqual(val.repository_id(), self._repository_id)
                # TODO: use constants instead of strings
                self.assertEqual(sorted(val.keys()),
                    sorted([DocumentFactory.DOCUMENT_USERNAME_ID,
                        Document.DOCUMENT_REPOSITORY_ID,
                        Document.DOCUMENT_DESCRIPTION_ID,
                        Document.DOCUMENT_TITLE_ID,
                        Document.DOCUMENT_URL_ID,
                        Document.DOCUMENT_TIMESTAMP_ID,
                        Document.DOCUMENT_DOCUMENT_TYPE_ID,
                        Document.DOCUMENT_KEYWORDS_ID,
                        Document.DOCUMENT_DATA_ID,
                        Document.DOCUMENT_DOCUMENT_ID]))
                self.assert_(isinstance(
                    val[DocumentFactory.DOCUMENT_USERNAME_ID],
                        const_get_stringtype()))
                self.assert_(isinstance(val[Document.DOCUMENT_REPOSITORY_ID],
                    const_get_stringtype()))
                self.assert_(isinstance(val[Document.DOCUMENT_TITLE_ID],
                    const_get_stringtype()))
                self.assert_(isinstance(val[Document.DOCUMENT_DESCRIPTION_ID],
                    const_get_stringtype()))
                self.assert_(isinstance(val[Document.DOCUMENT_TIMESTAMP_ID],
                    float))
                self.assert_(isinstance(val[Document.DOCUMENT_DOCUMENT_TYPE_ID],
                    int))
                self.assert_(isinstance(val[Document.DOCUMENT_DOCUMENT_ID],
                    int))
                self.assert_(isinstance(val[Document.DOCUMENT_DATA_ID],
                    const_get_stringtype()))
                self.assert_(isinstance(val[Document.DOCUMENT_KEYWORDS_ID],
                    const_get_stringtype()))
                if val[Document.DOCUMENT_URL_ID]:
                    self.assert_(isinstance(val[Document.DOCUMENT_URL_ID], 
                        const_get_stringtype()))
                else:
                    self.assert_(val[Document.DOCUMENT_URL_ID] is None)

    def test_get_icons(self):
        pk = self._real_package_name
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        docs = webserv.get_icons([pk], cache = False)
        self.assert_(pk in docs)
        self.assert_(isinstance(docs[pk], DocumentList))
        for vals in docs.values():
            for val in vals:
                self.assert_(isinstance(val, Document))
                self.assert_(val.is_icon())
                self.assert_(not val.is_image())

    def test_get_comments(self):
        pk = self._real_package_name
        webserv = self._factory.new(self._repository_id)
        docs = webserv.get_comments([pk], cache = False)
        self.assert_(pk in docs)
        self.assert_(docs[pk])
        for vals in docs.values():
            for val in vals:
                self.assert_(isinstance(val, Document))
                self.assert_(val.is_comment())

    def test_report_error(self):
        params = {}
        params['arch'] = etpConst['currentarch']
        params['stacktrace'] = "zomg Vogons!"
        params['name'] = "Ford Prefect"
        params['email'] = "ford@betelgeuse.gal"
        params['version'] = etpConst['entropyversion']
        params['errordata'] = "towel forgotten"
        params['description'] = "don't panic"
        params['arguments'] = ' '.join(sys.argv)
        params['uid'] = etpConst['uid']
        params['system_version'] = "N/A"
        params['system_version'] = "42"
        params['processes'] = "none"
        params['lsof'] = "none"
        params['lspci'] = "none"
        params['dmesg'] = "none"
        params['locale'] = "Vogonish"
        params['repositories.conf'] = "empty"
        params['client.conf'] = "---NA---"
        webserv = self._factory.new(self._repository_id)
        outcome = webserv.report_error(params)
        self.assertEqual(outcome, None)

    def test_data_send_available(self):
        webserv = self._factory.new(self._repository_id)
        self.assertEqual(webserv.data_send_available(), True)

    def test_factory_comment(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"
        doc = doc_factory.comment("username", "comment", "title", keywords)
        self.assert_(doc.is_comment())
        self.assert_(not doc.is_image())
        self.assert_(not doc.is_icon())
        self.assert_(not doc.is_file())
        self.assert_(not doc.is_video())
        self.assertEqual(doc.document_id(), None) # it's new!
        self.assertEqual(doc.repository_id(), self._repository_id)
        self.assertEqual(doc.document_type(), Document.COMMENT_TYPE_ID)
        self.assertEqual(doc.document_keywords(), keywords)
        self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID], "username")
        self.assertEqual(doc[Document.DOCUMENT_DATA_ID], "comment")
        self.assertEqual(doc[Document.DOCUMENT_TITLE_ID], "title")

    def test_factory_image(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.image("username", tmp_f, "title",
                    "description", keywords)
                self.assert_(not doc.is_comment())
                self.assert_(doc.is_image())
                self.assert_(not doc.is_icon())
                self.assert_(not doc.is_file())
                self.assert_(not doc.is_video())
                self.assertEqual(doc.document_id(), None) # it's new!
                self.assertEqual(doc.repository_id(), self._repository_id)
                self.assertEqual(doc.document_type(), Document.IMAGE_TYPE_ID)
                self.assertEqual(doc.document_keywords(), keywords)
                self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID],
                    "username")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_PAYLOAD_ID],
                    (os.path.basename(tmp_f.name), tmp_f))
                self.assertEqual(doc[Document.DOCUMENT_TITLE_ID], "title")
                self.assertEqual(doc[Document.DOCUMENT_DESCRIPTION_ID],
                    "description")
        finally:
            os.remove(tmp_path)

    def test_factory_icon(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.icon("username", tmp_f, "title",
                    "description", keywords)
                self.assert_(not doc.is_comment())
                self.assert_(not doc.is_image())
                self.assert_(doc.is_icon())
                self.assert_(not doc.is_file())
                self.assert_(not doc.is_video())
                self.assertEqual(doc.document_id(), None) # it's new!
                self.assertEqual(doc.repository_id(), self._repository_id)
                self.assertEqual(doc.document_type(), Document.ICON_TYPE_ID)
                self.assertEqual(doc.document_keywords(), keywords)
                self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID],
                    "username")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_PAYLOAD_ID],
                    (os.path.basename(tmp_f.name), tmp_f))
                self.assertEqual(doc[Document.DOCUMENT_TITLE_ID],
                    "title")
                self.assertEqual(doc[Document.DOCUMENT_DESCRIPTION_ID],
                    "description")
        finally:
            os.remove(tmp_path)

    def test_factory_file(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.file("username", tmp_f, "title",
                    "description", keywords)
                self.assert_(not doc.is_comment())
                self.assert_(not doc.is_image())
                self.assert_(not doc.is_icon())
                self.assert_(doc.is_file())
                self.assert_(not doc.is_video())
                self.assertEqual(doc.document_id(), None) # it's new!
                self.assertEqual(doc.repository_id(), self._repository_id)
                self.assertEqual(doc.document_type(), Document.FILE_TYPE_ID)
                self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID],
                    "username")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_PAYLOAD_ID],
                    (os.path.basename(tmp_f.name), tmp_f))
                self.assertEqual(doc[Document.DOCUMENT_TITLE_ID],
                    "title")
                self.assertEqual(doc[Document.DOCUMENT_DESCRIPTION_ID],
                    "description")
                self.assertEqual(doc.document_keywords(), keywords)
        finally:
            os.remove(tmp_path)

    def test_factory_video(self):
        webserv = self._factory.new(self._repository_id)
        self.assert_(webserv.service_available(cache = False))
        doc_factory = webserv.document_factory()
        keywords = "keyword1 keyword2"

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.video("username", tmp_f, "title",
                    "description", keywords)
                self.assert_(not doc.is_comment())
                self.assert_(not doc.is_image())
                self.assert_(not doc.is_icon())
                self.assert_(not doc.is_file())
                self.assert_(doc.is_video())
                self.assertEqual(doc.document_id(), None) # it's new!
                self.assertEqual(doc.repository_id(), self._repository_id)
                self.assertEqual(doc.document_type(), Document.VIDEO_TYPE_ID)
                self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID],
                    "username")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_PAYLOAD_ID],
                    (os.path.basename(tmp_f.name), tmp_f))
                self.assertEqual(doc[Document.DOCUMENT_TITLE_ID],
                    "title")
                self.assertEqual(doc[Document.DOCUMENT_DESCRIPTION_ID],
                    "description")
                self.assertEqual(doc.document_keywords(), keywords)
        finally:
            os.remove(tmp_path)


if __name__ == '__main__':
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        from entropy.const import etpUi
        etpUi['debug'] = True
    unittest.main()
    entropy.tools.kill_threads()
    raise SystemExit(0)
