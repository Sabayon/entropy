# -*- coding: utf-8 -*-
import sys
import os
import tempfile
import unittest
sys.path.insert(0, '../')
sys.path.insert(0, '../../')

from entropy.client.interfaces import Client
from entropy.client.services.interfaces import Document, DocumentFactory
from entropy.const import etpConst, etpUi, const_convert_to_rawstring, \
    const_convert_to_unicode
import entropy.tools
import tests._misc as _misc

class EntropyRepositoryTest(unittest.TestCase):

    def setUp(self):
        sys.stdout.write("%s called\n" % (self,))
        sys.stdout.flush()
        self._entropy = Client(installed_repo = -1, indexing = False,
            xcache = False, repo_validation = False)
        self._factory = self._entropy.WebServices()
        self._repository_id = etpConst['officialrepositoryid']
        self._fake_user = "entropy_unittest"
        self._fake_pass = "entropy_unittest"
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
        webserv.add_credentials(user, password)
        self.assertEqual(webserv.get_credentials(), user)
        self.assertEqual(webserv.credentials_available(), True)
        self.assert_(webserv.remove_credentials())
        self.assertEqual(webserv.credentials_available(), False)

    def test_query_utf8(self):
        webserv = self._factory.new(self._repository_id)
        # this must not crash
        vote_data = webserv.get_votes([self._fake_package_name_utf8])

    def test_add_vote(self):
        webserv = self._factory.new(self._repository_id)
        # try with success
        webserv.remove_credentials()
        try:
            webserv.add_vote(self._fake_package_name, 4.0)
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            webserv.add_vote(self._fake_package_name, 4.0)
        finally:
            webserv.remove_credentials()

        # now check back if average vote is still 4.0
        vote = webserv.get_votes(
            [self._fake_package_name])[self._fake_package_name]
        self.assertEqual(vote, 4.0)

    def test_add_downloads(self):
        webserv = self._factory.new(self._repository_id)
        pk = self._fake_package_name
        pkg_list = [pk]
        cur_downloads = webserv.get_downloads(pkg_list)[pk]
        if cur_downloads is None:
            cur_downloads = 0

        self.assert_(webserv.add_downloads([self._fake_package_name]))

        # expect (cur_downloads + 1) now
        new_downloads = webserv.get_downloads(pkg_list)[pk]
        self.assertEqual(cur_downloads + 1, new_downloads)

    def test_add_icon(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()
        keywords = ["keyword1", "keyword2"]
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
                webserv.add_document(doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id])[doc_id]
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
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_TITLE_ID],
            remote_doc[DocumentFactory.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        self.assert_(
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID]))

    def test_add_image(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()
        keywords = ["keyword1", "keyword2"]
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
                webserv.add_document(doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id])[doc_id]
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
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_TITLE_ID],
            remote_doc[DocumentFactory.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        self.assert_(
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID]))

    def test_add_comment(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()
        keywords = ["keyword1", "keyword2"]
        comment = const_convert_to_unicode("comment hellò")
        title = const_convert_to_unicode("tìtle")

        doc = doc_factory.comment(self._fake_user, comment, title, keywords)
        webserv.remove_credentials()
        try:
            webserv.add_document(doc)
            # webserv.AuthenticationRequired should be raised
            self.assert_(False)
        except webserv.AuthenticationRequired:
            webserv.add_credentials(self._fake_user, self._fake_pass)
            self.assert_(webserv.credentials_available())
            self.assertEqual(webserv.get_credentials(), self._fake_user)
            # credentials must be valid
            webserv.validate_credentials()
            # now it should not crash
            new_doc = webserv.add_document(doc)
            # got the new document back, which is the same plus document_id
        finally:
            webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id])[doc_id]
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
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_TITLE_ID],
            remote_doc[DocumentFactory.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        self.assert_(
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID]))

    def test_add_file(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()
        keywords = ["keyword1", "keyword2"]
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
                webserv.add_document(doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id])[doc_id]
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
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_TITLE_ID],
            remote_doc[DocumentFactory.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        self.assert_(
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID]))

    def test_add_video(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()
        keywords = ["keyword1", "keyword2"]
        description = const_convert_to_unicode("descrìption")
        title = const_convert_to_unicode("tìtle")

        tmp_fd, tmp_path = tempfile.mkstemp()
        with open(tmp_path, "ab+") as tmp_f:
            tmp_f.write(const_convert_to_rawstring('MPEG4\x00\x00'))
            tmp_f.flush()
            tmp_f.seek(0)
            doc = doc_factory.video(self._fake_user, tmp_f, title,
                description, keywords)
            # do not actually publish the video
            doc['pretend'] = 1
            webserv.remove_credentials()
            try:
                webserv.add_document(doc)
                # webserv.AuthenticationRequired should be raised
                self.assert_(False)
            except webserv.AuthenticationRequired:
                webserv.add_credentials(self._fake_user, self._fake_pass)
                self.assert_(webserv.credentials_available())
                self.assertEqual(webserv.get_credentials(), self._fake_user)
                # credentials must be valid
                webserv.validate_credentials()
                # now it should not crash
                new_doc = webserv.add_document(doc)
                # got the new document back, which is the same plus document_id
            finally:
                webserv.remove_credentials()

        # now check back if document is there
        doc_id = new_doc[Document.DOCUMENT_DOCUMENT_ID]
        remote_doc = webserv.get_documents_by_id([doc_id])[doc_id]
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
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
            description)
        self.assertEqual(new_doc[DocumentFactory.DOCUMENT_TITLE_ID],
            remote_doc[DocumentFactory.DOCUMENT_TITLE_ID])
        self.assertEqual(remote_doc[DocumentFactory.DOCUMENT_TITLE_ID], title)
        self.assertEqual(new_doc.document_timestamp(),
            remote_doc.document_timestamp())
        self.assertEqual(new_doc.document_keywords(),
            remote_doc.document_keywords())

        # now try to remove
        self.assert_(
            webserv.remove_document(remote_doc[Document.DOCUMENT_DOCUMENT_ID]))

    def test_get_documents(self):
        pk = self._real_package_name
        webserv = self._factory.new(self._repository_id)
        docs = webserv.get_documents([pk], cache = False)
        self.assert_(pk in docs)
        self.assert_(docs[pk])
        for vals in docs.values():
            for val in vals:
                self.assert_(isinstance(val, Document))

    def test_get_comments(self):
        pk = self._real_package_name
        webserv = self._factory.new(self._repository_id)
        docs = webserv.get_comments([pk], cache = False)
        self.assert_(pk in docs)
        self.assert_(docs[pk])
        for vals in docs.values():
            for val in vals:
                self.assert_(isinstance(val, Document))

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
        doc_factory = webserv.document_factory()
        doc = doc_factory.comment("username", "comment", "title", ["a", "b"])
        self.assert_(doc.is_comment())
        self.assert_(not doc.is_image())
        self.assert_(not doc.is_icon())
        self.assert_(not doc.is_file())
        self.assert_(not doc.is_video())
        self.assertEqual(doc.document_id(), None) # it's new!
        self.assertEqual(doc.repository_id(), self._repository_id)
        self.assertEqual(doc.document_type(), Document.COMMENT_TYPE_ID)
        self.assertEqual(doc.document_keywords(), ["a", "b"])
        self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID], "username")
        self.assertEqual(doc[Document.DOCUMENT_DATA_ID], "comment")
        self.assertEqual(doc[DocumentFactory.DOCUMENT_TITLE_ID], "title")

    def test_factory_image(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.image("username", tmp_f, "title",
                    "description", ["a", "b"])
                self.assert_(not doc.is_comment())
                self.assert_(doc.is_image())
                self.assert_(not doc.is_icon())
                self.assert_(not doc.is_file())
                self.assert_(not doc.is_video())
                self.assertEqual(doc.document_id(), None) # it's new!
                self.assertEqual(doc.repository_id(), self._repository_id)
                self.assertEqual(doc.document_type(), Document.IMAGE_TYPE_ID)
                self.assertEqual(doc.document_keywords(), ["a", "b"])
                self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID],
                    "username")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_PAYLOAD_ID],
                    (os.path.basename(tmp_f.name), tmp_f))
                self.assertEqual(doc[DocumentFactory.DOCUMENT_TITLE_ID], "title")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
                    "description")
        finally:
            os.remove(tmp_path)

    def test_factory_icon(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.icon("username", tmp_f, "title",
                    "description", ["a", "b"])
                self.assert_(not doc.is_comment())
                self.assert_(not doc.is_image())
                self.assert_(doc.is_icon())
                self.assert_(not doc.is_file())
                self.assert_(not doc.is_video())
                self.assertEqual(doc.document_id(), None) # it's new!
                self.assertEqual(doc.repository_id(), self._repository_id)
                self.assertEqual(doc.document_type(), Document.ICON_TYPE_ID)
                self.assertEqual(doc.document_keywords(), ["a", "b"])
                self.assertEqual(doc[DocumentFactory.DOCUMENT_USERNAME_ID],
                    "username")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_PAYLOAD_ID],
                    (os.path.basename(tmp_f.name), tmp_f))
                self.assertEqual(doc[DocumentFactory.DOCUMENT_TITLE_ID],
                    "title")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
                    "description")
        finally:
            os.remove(tmp_path)

    def test_factory_file(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.file("username", tmp_f, "title",
                    "description", ["a", "b"])
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
                self.assertEqual(doc[DocumentFactory.DOCUMENT_TITLE_ID],
                    "title")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
                    "description")
                self.assertEqual(doc.document_keywords(), ["a", "b"])
        finally:
            os.remove(tmp_path)

    def test_factory_video(self):
        webserv = self._factory.new(self._repository_id)
        doc_factory = webserv.document_factory()

        tmp_fd, tmp_path = tempfile.mkstemp()
        try:
            with open(tmp_path, "ab+") as tmp_f:
                doc = doc_factory.video("username", tmp_f, "title",
                    "description", ["a", "b"])
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
                self.assertEqual(doc[DocumentFactory.DOCUMENT_TITLE_ID],
                    "title")
                self.assertEqual(doc[DocumentFactory.DOCUMENT_DESCRIPTION_ID],
                    "description")
                self.assertEqual(doc.document_keywords(), ["a", "b"])
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
