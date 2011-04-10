# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import os
from entropy.const import etpConst, const_isstring, const_convert_to_unicode
from entropy.output import bold, darkgreen, red, darkred, blue, purple, brown, \
    teal, print_info, print_warning, print_error
from entropy.services.client import WebService
from entropy.client.services.interfaces import Document, DocumentFactory, \
    ClientWebService
from entropy.i18n import _
from text_tools import get_entropy_webservice as _get_service

import entropy.tools


def ugc(options):

    if not options:
        return -10

    cmd = options.pop(0)
    do_force = False
    myopts = []

    for opt in options:
        if opt == "--force":
            do_force = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        else:
            myopts.append(opt)

    options = myopts
    rc = -10

    from entropy.client.interfaces import Client
    entropy_client = None
    try:
        entropy_client = Client()
        if cmd == "login":
            if options:
                rc = _ugc_login(entropy_client, options[0],
                    force = do_force)
        elif cmd == "logout":
            if options:
                rc = _ugc_logout(entropy_client, options[0])
        elif cmd == "documents":
            if options:
                rc = _ugc_documents(entropy_client, options)
        elif cmd == "vote":
            if options:
                rc = _ugc_votes(entropy_client, options)
    finally:
        if entropy_client is not None:
            entropy_client.shutdown()

    return rc


def _ugc_login(entropy_client, repository, force = False):

    if repository not in entropy_client.repositories():
        print_error(red("%s: %s." % (_("Invalid repository"), repository,)))
        return 1

    try:
        webserv = _get_service(entropy_client, repository, tx_cb = True)
    except WebService.UnsupportedService:
        print_info(
            "[%s] %s." % (
                darkgreen(repository),
                blue(_("Repository does not support Entropy Services.")),
            )
        )
        return 1

    username = webserv.get_credentials()
    if (username is not None) and not force:
        print_info(
            "[%s] %s %s. %s." % (
                darkgreen(repository),
                blue(_("Already logged in as")),
                bold(login_data[0]),
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
        print_warning(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Login aborted. Not logged in.")),
            )
        )
        return 1

    username, password = login_data['username'], login_data['password']
    webserv.add_credentials(username, password)
    try:
        webserv.validate_credentials()
    except WebService.AuthenticationFailed:
        print_warning(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Authentication error. Not logged in.")),
            )
        )
        return 1

    print_info(
        "[%s:uid:%s] %s: %s." % (
            darkgreen(repository),
            etpConst['uid'],
            blue(_("Successfully logged in as")),
            bold(username)
        )
    )
    print_info(
        "%s." % (
            blue(_("From now on, any UGC action will be committed as this user"))
        )
    )
    return 0


def _ugc_logout(entropy_client, repository):

    if repository not in entropy_client.repositories():
        print_error(red("%s: %s." % (_("Invalid repository"), repository,)))
        return 1

    try:
        webserv = _get_service(entropy_client, repository)
    except WebService.UnsupportedService:
        print_info(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Repository does not support Entropy Services.")),
            )
        )
        return 1

    username = webserv.get_credentials()
    if username is None:
        print_info(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Not logged in.")),
            )
        )
        return 0

    webserv.remove_credentials()
    print_info(
        "[%s] %s %s %s" % (
            darkgreen(repository),
            blue(_("User")),
            bold(username),
            blue(_("has been logged out.")),
        )
    )
    return 0

def _ugc_votes(entropy_client, options):

    rc = -10
    repository = options[0]
    options = options[1:]
    if not options:
        return rc
    cmd = options[0]
    options = options[1:]
    if not options:
        return rc
    pkgkey = options[0]
    options = options[1:]

    if repository not in entropy_client.repositories():
        print_error(red("%s: %s." % (_("Invalid repository"), repository,)))
        return 1

    try:
        webserv = _get_service(entropy_client, repository)
    except WebService.UnsupportedService:
        print_info(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Repository does not support Entropy Services.")),
            )
        )
        return 1

    username = webserv.get_credentials()
    if username is None:
        print_info(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Not logged in, please login first.")),
            )
        )
        return 0

    rc = 0
    if cmd == "get":

        try:
            vote = webserv.get_votes([pkgkey], cache = False)[pkgkey]
        except WebService.WebServiceException as err:
            print_error(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                )
            )
            return 1

        _show_vote(vote, repository, pkgkey)

    elif cmd == "add":

        print_info(" %s [%s] %s" % (
                bold("@@"),
                purple(pkgkey),
                blue(_("add vote")),
            )
        )
        def mycb(s):
            return s
        input_data = [('vote', darkred(_("Insert your vote (from 1 to 5)")),
            mycb, False)]

        data = entropy_client.input_box(
            blue("%s") % (_("Entropy UGC vote submission"),),
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
            print_error(
                "[%s] %s: %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    _("invalid vote, must be in range"),
                    " ".join([str(x) for x in ClientWebService.VALID_VOTES]),
                )
            )
            return 1

        print_info(" %s [%s] %s:" % (
                bold("@@"),
                purple(pkgkey),
                blue(_("Please review your submission")),
            )
        )
        print_info("  %s: %s" % (
                darkred(_("Vote")),
                blue(str(vote)),
            )
        )
        rc = entropy_client.ask_question(_("Do you want to submit?"))
        if rc != _("Yes"):
            return 1

        try:
            voted = webserv.add_vote(pkgkey, vote,
                clear_available_cache = True)
        except WebService.WebServiceException as err:
            print_error(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                )
            )
            return 1

        if not voted:
            print_error(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    _("already voted"),
                )
            )
            return 1
        else:
            print_info("[%s] %s" % (
                    purple(pkgkey),
                    blue(_("vote added, thank you!")),
                )
            )
            _ugc_votes(entropy_client, [repository, "get", pkgkey])

def _ugc_documents(entropy_client, options):

    repository = options[0]
    options = options[1:]
    if not options:
        return -10
    cmd = options[0]
    options = options[1:]
    if not options:
        return -10

    try:
        webserv = _get_service(entropy_client, repository, tx_cb = True)
    except WebService.UnsupportedService:
        print_info(
            "[%s] %s" % (
                darkgreen(repository),
                blue(_("Repository does not support Entropy Services.")),
            )
        )
        return 1

    if cmd == "get":

        pkgkey = options.pop(0)
        docs = []
        docs_offset = 0
        while True:
            try:
                docs_list = webserv.get_documents([pkgkey],
                    cache = False, offset = docs_offset)[pkgkey]
            except WebService.WebServiceException as err:
                print_error(
                    "[%s] %s: %s" % (
                        darkred(pkgkey),
                        blue(_("UGC error")),
                        err,
                    )
                )
                return 1
            if docs_list is None:
                print_error(
                    "[%s] %s: %s, %s" % (
                        darkred(pkgkey),
                        blue(_("UGC error")),
                        data,
                        err_string,
                    )
                )
                return 1
            docs.extend(docs_list)
            if not docs_list.has_more():
                break
            docs_offset += len(docs_list)

        try:
            downloads = webserv.get_downloads([pkgkey], cache = False)[pkgkey]
        except WebService.WebServiceException as err:
            print_error(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                )
            )
            return 1
        for doc in docs:
            _show_document(doc, repository, pkgkey)

        if docs:
            print_info(" %s %s: %s" % (
                    darkred("@@"),
                    blue(_("Number of downloads")),
                    downloads,
                )
            )
        else:
            print_info(" %s %s" % (
                    darkred("@@"),
                    blue(_("No User Generated Content available.")),
                )
            )
        return 0

    elif cmd == "add":

        pkgkey = options.pop(0)
        username = webserv.get_credentials()
        if username is None:
            print_info(
                "[%s] %s" % (
                    darkgreen(repository),
                    blue(_("Not logged in, please login first.")),
                )
            )
            return 0

        print_info(" %s [%s|%s] %s" % (
                bold("@@"),
                darkgreen(str(repository)),
                purple(str(pkgkey)),
                blue(_("Add document")),
            )
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
            return os.access(s, os.R_OK) and os.path.isfile(s)
        def types_cb(s):
            return s in my_quick_types

        input_data = [
            ('title', darkred(_("Insert document title")), mycb, False),
            ('description', darkred(_("Insert document description/comment")),
                mycb, False),
            ('keywords',
                darkred(_("Insert document's keywords (space separated)")),
                mycb, False),
            ('type', "%s [%s]" % (darkred(_("Choose document type")),
                ', '.join(["(%s) %s" % (brown(x[0]), darkgreen(x[1]),) for x \
                    in valid_types])), types_cb, False),
        ]
        data = entropy_client.input_box(
            blue("%s") % (_("Entropy UGC document submission"),),
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
                blue("%s") % (_("Entropy UGC document submission"),),
                input_data, cancel_button = True)
            if not u_data:
                return 1
            elif not isinstance(data, dict):
                return 1
            data['path'] = u_data['path']

        keywords = ', '.join(data['keywords'].split())
        # verify
        print_info(" %s [%s] %s:" % (
                bold("@@"),
                purple(pkgkey),
                blue(_("Please review your submission")),
            )
        )
        print_info("  %s: %s" % (
                darkred(_("Title")),
                blue(data['title']),
            )
        )
        print_info("  %s: %s" % (
                darkred(_("Description")),
                blue(data['description']),
            )
        )
        print_info("  %s: %s" % (
                darkred(_("Keywords")),
                blue(keywords),
            )
        )
        if data['path'] != None:
            print_info("  %s: %s" % (
                    darkred(_("Document path")),
                    blue(data['path']),
                )
            )
        print_info("  %s: (%s) %s" % (
                darkred(_("Document type")),
                darkred(doc_type[0]),
                blue(doc_type[1]),
            )
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
            print_error(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("Invalid document")),
                    err,
                )
            )
            if doc_f is not None:
                doc_f.close()
            return 1

        try:
            new_doc = webserv.add_document(pkgkey, doc)
        except WebService.WebServiceException as err:
            print_error(
                "[%s] %s: %s" % (
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    err,
                )
            )
            return 1
        finally:
            if doc_f is not None:
                doc_f.close()

        print_info(" %s [%s|id:%s] %s" % (
                bold("@@"),
                purple(pkgkey),
                new_doc.document_id(),
                blue(_("Document added, thank you!")),
            )
        )
        return 0

    elif cmd == "remove":

        print_info(" %s [%s] %s" % (
                bold("@@"),
                darkgreen(repository),
                blue(_("Documents removal")),
            )
        )
        print_info(" %s [%s] %s:" % (
                bold("@@"),
                darkgreen(repository),
                blue(_("Please review your submission")),
            )
        )
        print_info("  %s: %s" % (
                darkred(_("Document identifiers")),
                blue(', '.join(options)),
            )
        )
        identifiers = []
        for opt in options:
            try:
                identifiers.append(int(opt))
            except ValueError:
                pass
        if not identifiers:
            print_error(
                "[%s] %s: %s, %s" % (
                    darkgreen(repository),
                    blue(_("UGC error")),
                    _("No valid identifiers"),
                    options,
                )
            )
            return 1
        rc = entropy_client.ask_question(_("Would you like to review them?"))
        if rc == _("Yes"):
            try:
                docs_map = webserv.get_documents_by_id(identifiers,
                    cache = False)
            except WebService.WebServiceException as err:
                print_error(
                    "[%s] %s: %s" % (
                        darkred(str(identifiers)),
                        blue(_("UGC error")),
                        err,
                    )
                )
                return 1

            for pkgkey, doc in docs_map.items():
                if doc is None:
                    # doesn't exist
                    continue
                _show_document(doc, repository, pkgkey)

        rc = entropy_client.ask_question(
            _("Would you like to continue with the removal?"))
        if rc != _("Yes"):
            return 1

        try:
            docs_map = webserv.get_documents_by_id(identifiers,
                cache = False)
        except WebService.WebServiceException as err:
            print_error(
                "[%s] %s: %s" % (
                    darkred(str(identifiers)),
                    blue(_("UGC error")),
                    err,
                )
            )
            return 1

        for identifier in identifiers:
            doc = docs_map[identifier]
            if doc is None:
                print_error(
                    "[%s] %s: %s" % (
                        darkred(str(identifier)),
                        blue(_("UGC error")),
                        _("cannot get the requested Document"),
                    )
                )
                continue

            try:
                docs_map = webserv.remove_document(identifier)
            except WebService.WebServiceException as err:
                print_error(
                    "[%s] %s: %s" % (
                        darkred(str(identifiers)),
                        blue(_("UGC error")),
                        err,
                    )
                )
                continue

            print_info(
                "[%s] %s: %s" % (
                    darkred(str(identifier)),
                    blue(_("UGC status")),
                    _("removed successfully"),
                )
            )

        return 0

    return -10

def _show_document(doc, repository, pkgkey):

    title = const_convert_to_unicode(doc[Document.DOCUMENT_TITLE_ID])
    if not title:
        title = _("No title")
    title = darkgreen(title)
    ts = doc.document_timestamp()
    ts = entropy.tools.convert_unix_time_to_human_time(ts)

    print_info(" %s [%s|%s|%s|%s|%s|%s]" % (
            bold("@@"),
            bold(str(doc.document_id())),
            darkred(str(doc.document_type())),
            darkgreen(repository),
            purple(pkgkey),
            blue(doc[DocumentFactory.DOCUMENT_USERNAME_ID]),
            darkgreen(ts),
        )
    )
    print_info("\t%s: %s" % (
            blue(_("Title")),
            title,
        )
    )
    if const_isstring(doc.document_data()):
        text = doc.document_data()
    else:
        text = doc.document_data().tostring()
    text = const_convert_to_unicode(text)
    _my_formatted_print(text, "\t%s: " % (blue(_("Content")),), "\t")

    print_info("\t%s: %s" % (
            blue(_("Keywords")),
            doc.document_keywords(),
        )
    )
    url = doc.document_url()
    if url is not None:
        print_info("\t%s: %s" % (
                blue(_("Download")),
                url,
            )
        )

def _show_vote(vote, repository, pkgkey):
    if vote is None:
        vote = _("no votes")
    else:
        vote = str(vote)
    print_info(" %s [%s] %s: %s" % (
            bold("@@"),
            purple(pkgkey),
            darkred(_("current package vote")),
            darkgreen(vote),
        )
    )

def _my_formatted_print(data,header, reset_columns, min_chars = 25,
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
            print_info(desc_text)
            desc_text = reset_columns
    if fcount > 0:
        print_info(desc_text)
