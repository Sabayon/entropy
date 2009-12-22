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
    print_info, print_warning, print_error
from entropy.i18n import _
import entropy.tools

def ugc(options):

    if not options:
        return 0

    cmd = options.pop(0)
    do_force = False
    myopts = []

    for opt in options[1:]:
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
    entropy_client = Client()
    entropy_client.UGC.show_progress = True
    try:
        if cmd == "login":
            if options:
                rc = _ugc_login(entropy_client, options[0],
                    force = do_force)
        elif cmd == "logout":
            if options: rc = _ugc_logout(entropy_client, options[0])
        elif cmd == "documents":
            if options: rc = _ugc_documents(entropy_client, options)
        elif cmd == "vote":
            if options: rc = _ugc_votes(entropy_client, options)
    finally:
        entropy_client.destroy()

    return rc


def _ugc_login(entropy_client, repository, force = False):

    if repository not in entropy_client.validRepositories:
        print_error(red("%s: %s." % (_("Invalid repository"), repository,)))
        entropy_client.UGC.remove_login(repository)
        return 1

    login_data = entropy_client.UGC.read_login(repository)
    if (login_data != None) and not force:
        print_info(
            "[%s] %s %s. %s." % (
                darkgreen(repository),
                blue(_("Already logged in as")),
                bold(login_data[0]),
                blue(_("Please logout first"))
            )
        )
        return 0
    elif (login_data != None) and force:
        entropy_client.UGC.remove_login(repository)

    status, msg = entropy_client.UGC.login(repository)
    if status:
        login_data = entropy_client.UGC.read_login(repository)
        print_info(
            "[%s:uid:%s] %s: %s. %s." % (
                darkgreen(repository),
                etpConst['uid'],
                blue(_("Successfully logged in as")),
                bold(login_data[0]),
                blue(_("From now on, any UGC action will be committed as this user"))
            )
        )
        return 0
    else:
        print_info(
            "[%s] %s." % (
                darkgreen(repository),
                blue(_("Login error. Not logged in.")),
            )
        )
        return 1


def _ugc_logout(entropy_client, repository):

    if repository not in entropy_client.validRepositories:
        print_error(red("%s: %s." % (_("Invalid repository"), repository,)))
        return 1

    login_data = entropy_client.UGC.read_login(repository)
    if login_data == None:
        print_info(
            "[%s] %s." % (
                darkgreen(repository),
                blue(_("Not logged in")),
            )
        )
    else:
        entropy_client.UGC.remove_login(repository)
        print_info(
            "[%s] %s %s %s." % (
                darkgreen(repository),
                blue(_("User")),
                bold(login_data[0]),
                blue(_("has been logged out")),
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

    rc = 0
    if cmd == "get":

        data, err_string = entropy_client.UGC.get_vote(repository, pkgkey)
        if not isinstance(data, float):
            print_error(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    data,
                    err_string,
                )
            )
            return 1
        _show_vote(data, repository, pkgkey)

    elif cmd == "add":

        print_info(" %s [%s|%s] %s" % (
                bold("@@"),
                darkgreen(str(repository)),
                purple(str(pkgkey)),
                blue(_("Add vote")),
            )
        )
        def mycb(s):
            return s
        input_data = [('vote', darkred(_("Insert your vote (from 1 to 5)")),
            mycb, False)]

        data = entropy_client.inputBox(
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
        except ValueError:
            print_error(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    _("Vote not valid"),
                    data['vote'],
                )
            )
            return 1

        if vote not in etpConst['ugc_voterange']:
            print_error(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    _("Vote not in range"),
                    etpConst['ugc_voterange'],
                )
            )
            return 1

        # verify
        print_info(" %s [%s|%s] %s:" % (
                bold("@@"),
                darkgreen(str(repository)),
                purple(str(pkgkey)),
                blue(_("Please review your submission")),
            )
        )
        print_info("  %s: %s" % (
                darkred(_("Vote")),
                blue(str(vote)),
            )
        )
        rc = entropy_client.askQuestion(_("Do you want to submit?"))
        if rc != _("Yes"):
            return 1

        # submit vote
        voted, err_string = entropy_client.UGC.add_vote(
            repository, pkgkey, vote)
        if not voted:
            print_error(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    voted,
                    err_string,
                )
            )
            return 1
        else:
            print_info(" %s [%s|%s] %s" % (
                    bold("@@"),
                    darkgreen(str(repository)),
                    purple(str(pkgkey)),
                    blue(_("Vote added, thank you!")),
                )
            )
            _ugc_votes([repository, "get", pkgkey])

def _ugc_documents(entropy_client, options):

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
    rc = 0

    if cmd == "get":
        data, err_string = entropy_client.UGC.get_docs(repository, pkgkey)
        if not isinstance(data, (list, tuple)):
            print_error(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    data,
                    err_string,
                )
            )
            return 1
        downloads, err_string = entropy_client.UGC.get_downloads(
            repository, pkgkey)
        shown = False
        for comment_dict in data:
            shown = True
            _show_document(comment_dict, repository, comment_dict['pkgkey'])

        if shown:
            print_info(" %s %s: %s" % (
                    darkred("@@"),
                    blue(_("Number of downloads")),
                    downloads,
                )
            )
        else:
            print_info(" %s %s." % (
                    darkred("@@"),
                    blue(_("No User Generated Content available")),
                )
            )

    elif cmd == "add":

        print_info(" %s [%s|%s] %s" % (
                bold("@@"),
                darkgreen(str(repository)),
                purple(str(pkgkey)),
                blue(_("Add document")),
            )
        )
        valid_types = {
            ('c', _('text comment')): etpConst['ugc_doctypes']['comments'],
            ('f', _('simple file')): etpConst['ugc_doctypes']['generic_file'],
            ('i', _('simple image')): etpConst['ugc_doctypes']['image'],
            ('y', _('youtube video')): etpConst['ugc_doctypes']['youtube_video']
        }
        upload_needed_types = [
            etpConst['ugc_doctypes']['generic_file'],
            etpConst['ugc_doctypes']['image'],
            etpConst['ugc_doctypes']['youtube_video']
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
        data = entropy_client.inputBox(
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
            u_data = entropy_client.inputBox(
                blue("%s") % (_("Entropy UGC document submission"),),
                input_data, cancel_button = True)
            if not u_data:
                return 1
            elif not isinstance(data, dict):
                return 1
            data['path'] = u_data['path']

        keywords = ', '.join(data['keywords'].split())
        # verify
        print_info(" %s [%s|%s] %s:" % (
                bold("@@"),
                darkgreen(str(repository)),
                purple(str(pkgkey)),
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
        rc = entropy_client.askQuestion(_("Do you want to submit?"))
        if rc != _("Yes"):
            return 1

        # submit comment
        rslt, data = entropy_client.UGC.send_document_autosense(
            repository,
            pkgkey,
            data['type'],
            data['path'],
            data['title'],
            data['description'],
            data['keywords']
        )
        if not rslt:
            print_error(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(pkgkey),
                    blue(_("UGC error")),
                    rslt,
                    data,
                )
            )
            return 1
        else:
            if isinstance(data, tuple):
                iddoc, r_content = data
            else:
                iddoc = rslt
                r_content = data
            print_info(" %s [%s|%s|id:%s|%s] %s" % (
                    bold("@@"),
                    darkgreen(str(repository)),
                    purple(str(pkgkey)),
                    iddoc,
                    r_content,
                    blue(_("Document added, thank you!")),
                )
            )

    elif cmd == "remove":

        print_info(" %s [%s] %s" % (
                bold("@@"),
                darkgreen(str(repository)),
                blue(_("Documents removal")),
            )
        )
        print_info(" %s [%s] %s:" % (
                bold("@@"),
                darkgreen(str(repository)),
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
        rc = entropy_client.askQuestion(_("Would you like to review them?"))
        if rc == _("Yes"):
            data, err_msg = entropy_client.UGC.get_documents_by_identifiers(
                repository, identifiers)
            if not isinstance(data, tuple):
                print_error(
                    "[%s:%s] %s: %s, %s" % (
                        darkgreen(repository),
                        darkred(str(identifiers)),
                        blue(_("UGC error")),
                        data,
                        err_msg,
                    )
                )
                return 1
            for comment_dict in data:
                _show_document(comment_dict, repository, comment_dict['pkgkey'])

        rc = entropy_client.askQuestion(
            _("Would you like to continue with the removal?"))
        if rc != _("Yes"):
            return 1

        for identifier in identifiers:
            doc_data, err_msg = entropy_client.UGC.get_documents_by_identifiers(
                repository, [identifier])
            if not isinstance(doc_data, tuple):
                print_error(
                    "[%s:%s] %s: %s, %s" % (
                        darkgreen(repository),
                        darkred(str(identifier)),
                        blue(_("UGC error")),
                        doc_data,
                        err_msg,
                    )
                )
                continue
            doc_data = doc_data[0]
            data, err_msg = entropy_client.UGC.remove_document_autosense(
                repository, identifier, doc_data['iddoctype'])
            if data is False:
                print_error(
                    "[%s:%s] %s: %s, %s" % (
                        darkgreen(repository),
                        darkred(str(identifier)),
                        blue(_("UGC error")),
                        data,
                        err_msg,
                    )
                )
                continue
            print_info(
                "[%s:%s] %s: %s, %s" % (
                    darkgreen(repository),
                    darkred(str(identifier)),
                    blue(_("UGC status")),
                    data,
                    err_msg,
                )
            )


    return rc

def _show_document(mydict, repository, pkgkey):

    title = const_convert_to_unicode(mydict['title'])
    if not title:
        title = _("No title")
    title = darkgreen(title)
    doctype = None
    for item in etpConst['ugc_doctypes']:
        if etpConst['ugc_doctypes'][item] == mydict['iddoctype']:
            doctype = item
            break
    if doctype is None:
        doctype = _("Unknown type")

    print_info(" %s [%s|%s|%s|%s|%s|%s]" % (
            bold("@@"),
            bold(str(mydict['iddoc'])),
            darkred(str(doctype)),
            darkgreen(str(repository)),
            purple(str(pkgkey)),
            blue(mydict['username']),
            darkgreen(str(mydict['ts'])),
        )
    )
    print_info("\t%s: %s" % (
            blue(_("Title")),
            title,
        )
    )
    if const_isstring(mydict['ddata']):
        text = mydict['ddata']
    else:
        text = mydict['ddata'].tostring()
    text = const_convert_to_unicode(text)
    _my_formatted_print(text, "\t%s: " % (blue(_("Content")),), "\t")

    print_info("\t%s: %s" % (
            blue(_("Keywords")),
            ', '.join(mydict['keywords']),
        )
    )
    print_info("\t%s: %s" % (
            blue(_("Size")),
            entropy.tools.bytes_into_human(mydict['size']),
        )
    )
    if 'store_url' in mydict:
        if mydict['store_url'] != None:
            print_info("\t%s: %s" % (
                    blue(_("Download")),
                    mydict['store_url'],
                )
            )

def _show_vote(vote, repository, pkgkey):
    print_info(" %s [%s|%s] %s: %s" % (
            bold("@@"),
            darkgreen(str(repository)),
            purple(str(pkgkey)),
            darkred(_("Current package vote")),
            darkgreen(str(vote)),
        )
    )


def _my_formatted_print(data,header,reset_columns, min_chars = 25,
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
