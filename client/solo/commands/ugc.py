# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import sys
import argparse

from entropy.const import etpConst, const_isstring, \
    const_convert_to_unicode, const_file_readable
from entropy.i18n import _
from entropy.output import bold, darkgreen, red, darkred, blue, \
    purple, brown, teal
from entropy.services.client import WebService
from entropy.client.services.interfaces import Document, DocumentFactory, \
    ClientWebService

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand
from solo.utils import get_entropy_webservice as _get_service


class SoloUgc(SoloCommand):
    """
    Main Solo UGC command.
    """

    NAME = "ugc"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Manage User Generate Content (votes, comments, files).
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None
        self._commands = {}

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloUgc.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloUgc.NAME))

        subparsers = parser.add_subparsers(
            title="action", description=_("manage User Generated Content"),
            help=_("available commands"))

        login_parser = subparsers.add_parser(
            "login", help=_("login against the given repository"))
        login_parser.add_argument(
            "repo", help=_("repository name"))
        login_parser.add_argument(
            "--force", action="store_true",
            default=False, help=_("force action"))
        login_parser.set_defaults(func=self._login)
        _commands["login"] = {}

        logout_parser = subparsers.add_parser(
            "logout", help=_("logout from the given repository"))
        logout_parser.add_argument(
            "repo", help=_("repository name"))
        logout_parser.add_argument(
            "--force", action="store_true",
            default=False, help=_("force action"))
        logout_parser.set_defaults(func=self._logout)
        _commands["logout"] = {}

        documents_parser = subparsers.add_parser(
            "documents",
            help=_("manage package documents in "
                   "the selected repository (comments, files, videos)"))
        documents_parser.add_argument(
            "repo", help=_("repository name"))
        docs_d = {}
        _commands["documents"] = docs_d

        doc_subparsers = documents_parser.add_subparsers(
            title="action", description=_("manage Documents"),
            help=_("available commands"))

        doc_get_parser = doc_subparsers.add_parser(
            "get", help=_("get available documents for the "
                          "provided package name"))
        doc_get_parser.add_argument(
            "pkgkey", help=_("package name (example: x11-libs/qt)"))
        doc_get_parser.set_defaults(func=self._document_get)
        docs_d["get"] = {}

        doc_add_parser = doc_subparsers.add_parser(
            "add", help=_("add a new document to the "
                          "provided package name"))
        doc_add_parser.add_argument(
            "pkgkey", help=_("package name (example: x11-libs/qt)"))
        doc_add_parser.set_defaults(func=self._document_add)
        docs_d["add"] = {}

        doc_rm_parser = doc_subparsers.add_parser(
            "remove", help=_("remove documents from database "
                             "using their identifiers"))
        doc_rm_parser.add_argument(
            "pkgkey", help=_("package name (example: x11-libs/qt)"))
        doc_rm_parser.add_argument(
            "ids", nargs='+', metavar="<id>", type=int,
            help=_("document identifier"))
        doc_rm_parser.set_defaults(func=self._document_rm)
        docs_d["remove"] = {}


        vote_parser = subparsers.add_parser(
            "vote",
            help=_("manage package votes in "
                   "the selected repository"))
        vote_parser.add_argument(
            "repo", help=_("repository name"))
        vote_d = {}
        _commands["vote"] = vote_d

        vote_subparsers = vote_parser.add_subparsers(
            title="action", description=_("manage Votes"),
            help=_("available commands"))

        vote_get_parser = vote_subparsers.add_parser(
            "get", help=_("get vote for the provided package name"))
        vote_get_parser.add_argument(
            "pkgkey", help=_("package name (example: x11-libs/qt)"))
        vote_get_parser.set_defaults(func=self._vote_get)
        vote_d["get"] = {}

        vote_add_parser = vote_subparsers.add_parser(
            "add", help=_("add vote to the provided package name"))
        vote_add_parser.add_argument(
            "pkgkey", help=_("package name (example: x11-libs/qt)"))
        vote_add_parser.set_defaults(func=self._vote_add)
        vote_d["add"] = {}

        self._commands = _commands
        return parser

    def parse(self):
        """
        Parse command
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_shared, [nsargs.func]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    def _login(self, entropy_client):
        """
        Solo Ugc Login command.
        """
        repository = self._nsargs.repo
        force = self._nsargs.force

        if repository not in entropy_client.repositories():
            entropy_client.output(
                red("%s: %s." % (
                        _("Invalid repository"), repository,)),
                level="error", importance=1)
            return 1

        try:
            webserv = _get_service(
                entropy_client, repository, tx_cb = True)
        except WebService.UnsupportedService:
            entropy_client.output(
                "[%s] %s." % (
                    darkgreen(repository),
                    blue(_("Repository does not support Entropy Services.")),
                )
            )
            return 1

        username = webserv.get_credentials()
        if (username is not None) and not force:
            entropy_client.output(
                "[%s] %s %s. %s." % (
                    darkgreen(repository),
                    blue(_("Already logged in as")),
                    bold(username),
                    blue(_("Please logout first"))
                )
            )
            return 0
        elif (username is not None) and force:
            webserv.remove_credentials(repository)

        def fake_callback(*args, **kwargs):
            return True

        # use input box to read login
        input_params = [
            ('username', _('Username'), fake_callback, False),
            ('password', _('Password'), fake_callback, True)
        ]
        login_data = entropy_client.input_box(
            "%s %s %s" % (
                _('Please login against'), repository, _('repository'),),
            input_params,
            cancel_button = True
        )
        if not login_data:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Login aborted. Not logged in.")),
                ),
                level="warning", importance=1
            )
            return 1

        username, password = login_data['username'], login_data['password']
        webserv.add_credentials(username, password)
        try:
            webserv.validate_credentials()
        except WebService.AuthenticationFailed:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Authentication error. Not logged in.")),
                ),
                level="warning", importance=1
            )
            return 1
        except WebService.RequestError:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Communication error. Not logged in.")),
                ),
                level="warning", importance=1
            )
            return 1

        entropy_client.output(
            "[%s:uid:%s] %s: %s." % (
                darkgreen(repository),
                etpConst['uid'],
                blue(_("Successfully logged in as")),
                bold(username)
            )
        )
        entropy_client.output(
            "%s." % (
                blue(
                    _("From now on, any UGC action will "
                      "be committed as this user"))
            )
        )
        return 0

    def _logout(self, entropy_client):
        """
        Solo Ugc Logout command.
        """
        repository = self._nsargs.repo
        force = self._nsargs.force

        if repository not in entropy_client.repositories():
            entropy_client.output(
                "%s: %s." % (
                    darkred(_("Invalid repository")),
                    teal(repository),),
                level="error", importance=1)
            return 1

        try:
            webserv = _get_service(entropy_client, repository)
        except WebService.UnsupportedService:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Repository does not support Entropy Services.")),
                )
            )
            return 1

        username = webserv.get_credentials()
        if username is None:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Not logged in.")),
                )
            )
            return 0

        webserv.remove_credentials()
        entropy_client.output(
            "[%s] %s %s %s" % (
                darkgreen(repository),
                blue(_("User")),
                bold(username),
                blue(_("has been logged out.")),
            )
        )
        return 0

    def _show_document(self, entropy_client, doc, repository, pkgkey):

        title = const_convert_to_unicode(doc[Document.DOCUMENT_TITLE_ID])
        if not title:
            title = _("No title")
        title = darkgreen(title)
        ts = doc.document_timestamp()
        ts = entropy.tools.convert_unix_time_to_human_time(ts)

        entropy_client.output(" %s [%s|%s|%s|%s|%s|%s]" % (
                bold("@@"),
                bold(str(doc.document_id())),
                darkred(str(doc.document_type())),
                darkgreen(repository),
                purple(pkgkey),
                blue(doc[DocumentFactory.DOCUMENT_USERNAME_ID]),
                darkgreen(ts),
            )
        )
        entropy_client.output("\t%s: %s" % (
                blue(_("Title")),
                title,
            )
        )
        if const_isstring(doc.document_data()):
            text = doc.document_data()
        else:
            text = doc.document_data().tostring()
        text = const_convert_to_unicode(text)
        self._formatted_print(
            entropy_client, text,
            "\t%s: " % (blue(_("Content")),), "\t")

        entropy_client.output("\t%s: %s" % (
                blue(_("Keywords")),
                doc.document_keywords(),
            )
        )
        url = doc.document_url()
        if url is not None:
            entropy_client.output("\t%s: %s" % (
                    blue(_("Download")),
                    url,
                )
            )

    def _show_vote(self, entropy_client, vote, repository, pkgkey):
        if vote is None:
            vote = _("no votes")
        else:
            vote = const_convert_to_unicode("%.2f" % (vote,))
        entropy_client.output(" %s [%s] %s: %s" % (
                bold(const_convert_to_unicode("@@")),
                purple(pkgkey),
                darkred(_("current package vote")),
                darkgreen(vote),
            )
        )

    def _formatted_print(self, entropy_client,
                         data, header, reset_columns, min_chars = 25,
                         color = None):
        if isinstance(data, set):
            mydata = list(data)
        elif not isinstance(data, list):
            mydata = data.split()
        else:
            mydata = data

        fcount = 0
        desc_text = header
        for x in mydata:
            fcount += len(x)
            if color:
                desc_text += color(x)+" "
            else:
                desc_text += x+" "
            if fcount > min_chars:
                fcount = 0
                entropy_client.output(desc_text)
                desc_text = reset_columns
        if fcount > 0:
            entropy_client.output(desc_text)

    def _document_get(self, entropy_client):
        """
        Solo Ugc Document Get command.
        """
        pkgkey = self._nsargs.pkgkey
        repository = self._nsargs.repo

        try:
            webserv = _get_service(
                entropy_client, repository, tx_cb = True)
        except WebService.UnsupportedService:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Repository does not "
                           "support Entropy Services.")),
                    ),
                level="warning", importance=1
                )
            return 1

        docs = []
        docs_offset = 0
        while True:
            try:
                docs_list = webserv.get_documents([pkgkey],
                    cache = False, offset = docs_offset)[pkgkey]
            except WebService.WebServiceException as err:
                entropy_client.output(
                    "[%s] %s: %s" % (
                        darkred(pkgkey),
                        blue(_("UGC error")),
                        err,
                    ),
                    level="error", importance=1
                )
                return 1
            if docs_list is None:
                entropy_client.output(
                    "[%s] %s: NULL list" % (
                        darkred(pkgkey),
                        blue(_("UGC error")),
                    ),
                    level="error", importance=1
                )
                return 1
            docs.extend(docs_list)
            if not docs_list.has_more():
                break
            docs_offset += len(docs_list)

        try:
            downloads = webserv.get_downloads(
                [pkgkey], cache = False)[pkgkey]
        except WebService.WebServiceException as err:
            entropy_client.output(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                ),
                level="error", importance=1
            )
            return 1
        for doc in docs:
            self._show_document(entropy_client, doc, repository, pkgkey)

        if docs:
            entropy_client.output(
                "%s: %s" % (
                    blue(_("Number of downloads")),
                    downloads,
                    ),
                header=darkred(" @@ ")
            )
        else:
            entropy_client.output(
                blue(_("No User Generated Content available.")),
                header=darkred(" @@ ")
            )
        return 0

    def _document_add(self, entropy_client):
        """
        Solo Ugc Document Add command.
        """
        pkgkey = self._nsargs.pkgkey
        repository = self._nsargs.repo

        try:
            webserv = _get_service(
                entropy_client, repository, tx_cb = True)
        except WebService.UnsupportedService:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Repository does not "
                           "support Entropy Services.")),
                    ),
                level="warning", importance=1
                )
            return 1

        username = webserv.get_credentials()
        if username is None:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Not logged in, please login first.")),
                ),
                level="error", importance=1
            )
            return 1

        entropy_client.output(
            "[%s|%s] %s" % (
                darkgreen(str(repository)),
                purple(str(pkgkey)),
                blue(_("Add document")),
                ),
            header=bold(" @@ ")
        )
        valid_types = {
            ('c', _('text comment')): Document.COMMENT_TYPE_ID,
            ('o', _('icon')): Document.ICON_TYPE_ID,
            ('f', _('simple file')): Document.FILE_TYPE_ID,
            ('i', _('simple image')): Document.IMAGE_TYPE_ID,
            ('y', _('video')): Document.VIDEO_TYPE_ID,
        }
        upload_needed_types = [
            Document.FILE_TYPE_ID,
            Document.IMAGE_TYPE_ID,
            Document.ICON_TYPE_ID,
            Document.VIDEO_TYPE_ID
        ]
        my_quick_types = [x[0] for x in valid_types]
        def mycb(s):
            return s
        def path_cb(s):
            return const_file_readable(s)
        def types_cb(s):
            return s in my_quick_types

        input_data = [
            ('title', darkred(_("Insert document title")), mycb, False),
            ('description',
                darkred(_("Insert document description/comment")),
                mycb, False),
            ('keywords',
                darkred(_("Insert document's keywords (space separated)")),
                mycb, False),
            ('type', "%s [%s]" % (darkred(_("Choose document type")),
                ', '.join(["(%s) %s" % (brown(x[0]), darkgreen(x[1]),) \
                    for x in valid_types])), types_cb, False),
        ]
        data = entropy_client.input_box(
            blue(_("Entropy UGC document submission")),
            input_data, cancel_button = True)

        if not data:
            return 1
        elif not isinstance(data, dict):
            return 1

        doc_type = None
        for myshort, mylong in valid_types:
            if data['type'] == myshort:
                doc_type = (myshort, mylong)
                data['type'] = valid_types.get((myshort, mylong,))
                break

        data['path'] = None
        if data['type'] in upload_needed_types:
            input_data = [('path', darkred(_("Insert document path")),
                path_cb, False)]
            u_data = entropy_client.input_box(
                blue(_("Entropy UGC document submission")),
                input_data, cancel_button = True)
            if not u_data:
                return 1
            elif not isinstance(data, dict):
                return 1
            data['path'] = u_data['path']

        keywords = ', '.join(data['keywords'].split())
        # verify
        entropy_client.output(
            "[%s] %s:" % (
                purple(pkgkey),
                blue(_("Please review your submission")),
            ),
            header=bold(" @@ ")
        )
        entropy_client.output(
            "%s: %s" % (
                darkred(_("Title")),
                blue(data['title']),
                ),
            header="  "
        )
        entropy_client.output(
            "%s: %s" % (
                darkred(_("Description")),
                blue(data['description']),
            ),
            header="  "
        )
        entropy_client.output(
            "%s: %s" % (
                darkred(_("Keywords")),
                blue(keywords),
            ),
            header="  "
        )
        if data['path'] != None:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Document path")),
                    blue(data['path']),
                    ),
                header="  "
            )
        entropy_client.output(
            "%s: (%s) %s" % (
                darkred(_("Document type")),
                darkred(doc_type[0]),
                blue(doc_type[1]),
                ),
            header="  "
        )
        rc = entropy_client.ask_question(_("Do you want to submit?"))
        if rc != _("Yes"):
            return 1

        doc_factory = DocumentFactory(repository)
        doc = None
        doc_f = None
        doc_type = data['type']
        try:
            if doc_type == Document.COMMENT_TYPE_ID:
                doc = doc_factory.comment(username, data['description'],
                    data['title'], data['keywords'])
            elif doc_type == Document.ICON_TYPE_ID:
                doc_f = open(data['path'], "rb")
                doc = doc_factory.icon(username, doc_f, data['title'],
                    data['description'], data['keywords'])
            elif doc_type == Document.FILE_TYPE_ID:
                doc_f = open(data['path'], "rb")
                doc = doc_factory.file(username, doc_f, data['title'],
                    data['description'], data['keywords'])
            elif doc_type == Document.IMAGE_TYPE_ID:
                doc_f = open(data['path'], "rb")
                doc = doc_factory.image(username, doc_f, data['title'],
                    data['description'], data['keywords'])
            elif doc_type == Document.VIDEO_TYPE_ID:
                doc_f = open(data['path'], "rb")
                doc = doc_factory.video(username, doc_f, data['title'],
                    data['description'], data['keywords'])
        except AssertionError as err:
            entropy_client.output(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("Invalid document")),
                    err,
                ),
                level="error", importance=1
            )
            if doc_f is not None:
                doc_f.close()
            return 1

        try:
            new_doc = webserv.add_document(pkgkey, doc)
        except WebService.WebServiceException as err:
            entropy_client.output(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                ),
                level="error", importance=1
            )
            return 1
        finally:
            if doc_f is not None:
                doc_f.close()

        entropy_client.output(
            "[%s|id:%s] %s" % (
                purple(pkgkey),
                new_doc.document_id(),
                blue(_("Document added, thank you!")),
            ),
            header=bold(" @@ ")
        )
        return 0

    def _document_rm(self, entropy_client):
        """
        Solo Ugc Document Rm command.
        """
        pkgkey = self._nsargs.pkgkey
        repository = self._nsargs.repo
        document_ids = self._nsargs.ids

        try:
            webserv = _get_service(
                entropy_client, repository, tx_cb = True)
        except WebService.UnsupportedService:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Repository does not "
                           "support Entropy Services.")),
                    ),
                level="warning", importance=1
                )
            return 1

        entropy_client.output(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Documents removal")),
            ),
            header=bold(" @@ ")
        )
        entropy_client.output(
            "[%s] %s:" % (
                darkgreen(repository),
                blue(_("Please review your submission")),
                ),
            header=bold(" @@ ")
        )
        entropy_client.output(
            "  %s: %s" % (
                darkred(_("Document identifiers")),
                blue(', '.join(document_ids)),
            )
        )
        rc = entropy_client.ask_question(
            _("Would you like to review them?"))
        if rc == _("Yes"):
            try:
                docs_map = webserv.get_documents_by_id(document_ids,
                    cache = False)
            except WebService.WebServiceException as err:
                entropy_client.output(
                    "%s: %s" % (
                        blue(_("UGC error")),
                        err,
                    ),
                    level="error", importance=1
                )
                return 1

            for pkgkey, doc in docs_map.items():
                if doc is None:
                    # doesn't exist
                    continue
                self._show_document(entropy_client,
                                    doc, repository, pkgkey)

        rc = entropy_client.ask_question(
            _("Would you like to continue with the removal?"))
        if rc != _("Yes"):
            return 1

        try:
            docs_map = webserv.get_documents_by_id(document_ids,
                cache = False)
        except WebService.WebServiceException as err:
            entropy_client.output(
                "%s: %s" % (
                    blue(_("UGC error")),
                    err,
                ),
                level="error", importance=1
            )
            return 1

        for identifier in document_ids:
            doc = docs_map[identifier]
            if doc is None:
                entropy_client.output(
                    "%s: %s" % (
                        blue(_("UGC error")),
                        _("cannot get the requested Document"),
                    ),
                    level="error", importance=1
                )
                continue

            try:
                docs_map = webserv.remove_document(identifier)
            except WebService.WebServiceException as err:
                entropy_client.output(
                    "%s: %s" % (
                        blue(_("UGC error")),
                        err,
                    ),
                    level="error", importance=1
                )
                continue

            entropy_client.output(
                "%s: %s" % (
                    blue(_("UGC status")),
                    _("removed successfully"),
                ),
                level="error", importance=1
            )

        return 0

    def _vote_get(self, entropy_client):
        """
        Solo Ugc Vote Get command.
        """
        pkgkey = self._nsargs.pkgkey
        repository = self._nsargs.repo

        try:
            webserv = _get_service(
                entropy_client, repository,
                tx_cb = True)
        except WebService.UnsupportedService:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Repository does not "
                           "support Entropy Services.")),
                    ),
                level="warning", importance=1
                )
            return 1

        try:
            vote = webserv.get_votes([pkgkey], cache = False)[pkgkey]
        except WebService.WebServiceException as err:
            entropy_client.output(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                ),
                level="error", importance=1
            )
            return 1

        self._show_vote(entropy_client, vote, repository, pkgkey)
        return 0

    def _vote_add(self, entropy_client):
        """
        Solo Ugc Vote Add command.
        """
        pkgkey = self._nsargs.pkgkey
        repository = self._nsargs.repo

        try:
            webserv = _get_service(
                entropy_client, repository,
                tx_cb = True)
        except WebService.UnsupportedService:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Repository does not "
                           "support Entropy Services.")),
                    ),
                level="warning", importance=1
                )
            return 1

        username = webserv.get_credentials()
        if username is None:
            entropy_client.output(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Not logged in, please login first.")),
                ),
                level="warning", importance=1
            )
            return 1

        entropy_client.output(
            "[%s] %s" % (
                purple(pkgkey),
                blue(_("add vote")),
            ),
            header=bold(" @@ ")
        )
        def mycb(s):
            return s
        input_data = [
            ('vote',
             darkred(_("Insert your vote (from 1 to 5)")),
             mycb, False)]

        data = entropy_client.input_box(
            blue(_("Entropy UGC vote submission")),
            input_data, cancel_button = True)

        if not data:
            return 1
        elif not isinstance(data, dict):
            return 1
        elif 'vote' not in data:
            return 1
        elif not data['vote']:
            return 1

        try:
            vote = int(data['vote'])
            if vote not in ClientWebService.VALID_VOTES:
                raise ValueError()
        except ValueError:
            entropy_client.output(
                "[%s] %s: %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    _("invalid vote, must be in range"),
                    " ".join([str(x) for x in \
                                  ClientWebService.VALID_VOTES]),
                    ),
                level="error", importance=1
            )
            return 1

        entropy_client.output(
            "[%s] %s:" % (
                purple(pkgkey),
                blue(_("Please review your submission")),
            ),
            header=bold(" @@ ")
        )
        entropy_client.output(
            "%s: %s" % (
                darkred(_("Vote")),
                blue(const_convert_to_unicode(vote)),
                ),
            header="  "
        )
        rc = entropy_client.ask_question(
            _("Do you want to submit?"))
        if rc != _("Yes"):
            return 1

        try:
            voted = webserv.add_vote(pkgkey, vote,
                clear_available_cache = True)
        except WebService.WebServiceException as err:
            entropy_client.output(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                ),
                level="error", importance=1
            )
            return 1

        if not voted:
            entropy_client.output(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    _("already voted"),
                ),
                level="error", importance=1
            )
            return 1
        else:
            entropy_client.output("[%s] %s" % (
                    purple(pkgkey),
                    blue(_("vote added, thank you!")),
                )
            )
            self._vote_get(entropy_client)

        return 0

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloUgc,
        SoloUgc.NAME,
        _("manage User Generated Content"))
    )
