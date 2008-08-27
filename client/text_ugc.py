#!/usr/bin/python
'''
    Copyright (C) 2007-2008 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

from entropyConstants import *
from outputTools import *
from entropy import EquoInterface
from entropy_i18n import _
Equo = EquoInterface()
Equo.UGC.show_progress = True


def ugc(options):

    if len(options) < 1:
        return 0
    cmd = options[0]
    do_force = False
    myopts = []
    for opt in options[1:]:
        if opt == "--force":
            do_force = True
        else:
            myopts.append(opt)
    options = myopts
    rc = -10

    if cmd == "login":
        if options: rc = ugcLogin(options[0], force = do_force)
    elif cmd == "logout":
        if options: rc = ugcLogout(options[0])
    elif cmd == "documents":
        if options: rc = ugcDocuments(options)
    elif cmd == "vote":
        if options: rc = ugcVotes(options)

    return rc


def ugcLogin(repository, force = False):

    if repository not in Equo.validRepositories:
        print_error(red("%s: %s." % (_("Invalid repository"),repository,)))
        Equo.UGC.remove_login(repository)
        return 1

    login_data = Equo.UGC.read_login(repository)
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
        Equo.UGC.remove_login(repository)

    status, msg = Equo.UGC.login(repository)
    if status:
        login_data = Equo.UGC.read_login(repository)
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


def ugcLogout(repository):

    if repository not in Equo.validRepositories:
        print_error(red("%s: %s." % (_("Invalid repository"),repository,)))
        return 1

    login_data = Equo.UGC.read_login(repository)
    if login_data == None:
        print_info(
            "[%s] %s." % (
                darkgreen(repository),
                blue(_("Not logged in")),
            )
        )
    else:
        Equo.UGC.remove_login(repository)
        print_info(
            "[%s] %s %s %s." % (
                darkgreen(repository),
                blue(_("User")),
                bold(login_data[0]),
                blue(_("has been logged out")),
            )
        )
    return 0

def ugcVotes(options):

    rc = -10
    repository = options[0]
    options = options[1:]
    if not options: return rc
    cmd = options[0]
    options = options[1:]
    if not options: return rc
    pkgkey = options[0]
    options = options[1:]

    rc = 0
    if cmd == "get":

        data, err_string = Equo.UGC.get_vote(repository, pkgkey)
        if not isinstance(data,float):
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
        showVote(data, repository, pkgkey)

    elif cmd == "add":

        print_info(" %s [%s|%s] %s" % (
                bold(u"@@"),
                darkgreen(unicode(repository)),
                purple(unicode(pkgkey)),
                blue(_("Add vote")),
            )
        )
        def mycb(s):
            return s
        input_data = [('vote',darkred(_("Insert your vote (from 1 to 5)")),mycb,False)]

        data = Equo.inputBox(blue("%s") % (_("Entropy UGC vote submission"),), input_data, cancel_button = True)

        if not data:
            return 1
        elif not isinstance(data,dict):
            return 1
        elif not data.has_key('vote'):
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
                bold(u"@@"),
                darkgreen(unicode(repository)),
                purple(unicode(pkgkey)),
                blue(_("Please review your submission")),
            )
        )
        print_info("  %s: %s" % (
                darkred(_("Vote")),
                blue(str(vote)),
            )
        )
        rc = Equo.askQuestion("Do you want to submit?")
        if rc != "Yes":
            return 1

        # submit vote
        voted, err_string = Equo.UGC.add_vote(repository, pkgkey, vote)
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
                    bold(u"@@"),
                    darkgreen(unicode(repository)),
                    purple(unicode(pkgkey)),
                    blue(_("Vote added, thank you!")),
                )
            )
            ugcVotes([repository,"get",pkgkey])

def ugcDocuments(options):

    rc = -10
    repository = options[0]
    options = options[1:]
    if not options: return rc
    cmd = options[0]
    options = options[1:]
    if not options: return rc
    pkgkey = options[0]
    options = options[1:]
    rc = 0

    if cmd == "get":
        data, err_string = Equo.UGC.get_docs(repository, pkgkey)
        if not isinstance(data,tuple):
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
        downloads, err_string = Equo.UGC.get_downloads(repository, pkgkey)
        shown = False
        for comment_dict in data:
            shown = True
            showDocument(comment_dict, repository, comment_dict['pkgkey'])

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
                bold(u"@@"),
                darkgreen(unicode(repository)),
                purple(unicode(pkgkey)),
                blue(_("Add document")),
            )
        )
        valid_types = {
            ('c',_('text comment')): etpConst['ugc_doctypes']['comments'],
            ('f',_('simple file')): etpConst['ugc_doctypes']['generic_file'],
            ('i',_('simple image')): etpConst['ugc_doctypes']['image'],
            ('y',_('youtube video')): etpConst['ugc_doctypes']['youtube_video']
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
            return os.access(s,os.R_OK)
        def types_cb(s):
            return s in my_quick_types

        input_data = [
            ('title',darkred(_("Insert document title")),mycb,False),
            ('description',darkred(_("Insert document description/comment")),mycb,False),
            ('keywords',darkred(_("Insert document's keywords (space separated)")),mycb,False),
            ('type',"%s [%s]" % (darkred(_("Choose document type")),', '.join(["(%s) %s" % (brown(x[0]),darkgreen(x[1]),) for x in valid_types])),types_cb,False),
        ]
        data = Equo.inputBox(blue("%s") % (_("Entropy UGC document submission"),), input_data, cancel_button = True)

        if not data:
            return 1
        elif not isinstance(data,dict):
            return 1

        doc_type = None
        for myshort,mylong in valid_types:
            if data['type'] == myshort:
                doc_type = (myshort,mylong)
                data['type'] = valid_types.get((myshort,mylong,))
                break

        data['path'] = None
        if data['type'] in upload_needed_types:
            input_data = [('path',darkred(_("Insert document path")),path_cb,False)]
            u_data = Equo.inputBox(blue("%s") % (_("Entropy UGC document submission"),), input_data, cancel_button = True)
            if not u_data:
                return 1
            elif not isinstance(data,dict):
                return 1
            data['path'] = u_data['path']

        keywords = ', '.join(data['keywords'].split())
        # verify
        print_info(" %s [%s|%s] %s:" % (
                bold(u"@@"),
                darkgreen(unicode(repository)),
                purple(unicode(pkgkey)),
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
        rc = Equo.askQuestion("Do you want to submit?")
        if rc != "Yes":
            return 1

        # submit comment
        rslt, data = Equo.UGC.send_document_autosense(
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
            if isinstance(data,tuple):
                iddoc, r_content = data
            else:
                iddoc = rslt
                r_content = data
            print_info(" %s [%s|%s|id:%s|%s] %s" % (
                    bold(u"@@"),
                    darkgreen(unicode(repository)),
                    purple(unicode(pkgkey)),
                    iddoc,
                    r_content,
                    blue(_("Document added, thank you!")),
                )
            )

    elif cmd == "remove":

        print_info(" %s [%s] %s" % (
                bold(u"@@"),
                darkgreen(unicode(repository)),
                blue(_("Documents removal")),
            )
        )
        print_info(" %s [%s] %s:" % (
                bold(u"@@"),
                darkgreen(unicode(repository)),
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
        rc = Equo.askQuestion("Would you like to review them?")
        if rc == "Yes":
            data, err_msg = Equo.UGC.get_documents_by_identifiers(repository, identifiers)
            if not isinstance(data,tuple):
                print_error(
                    "[%s:%s] %s: %s, %s" % (
                        darkgreen(repository),
                        darkred(unicode(identifiers)),
                        blue(_("UGC error")),
                        data,
                        err_msg,
                    )
                )
                return 1
            for comment_dict in data:
                showDocument(comment_dict, repository, comment_dict['pkgkey'])

        rc = Equo.askQuestion("Would you like to continue with the removal?")
        if rc != "Yes":
            return 1

        for identifier in identifiers:
            doc_data, err_msg = Equo.UGC.get_documents_by_identifiers(repository, [identifier])
            if not isinstance(doc_data,tuple):
                print_error(
                    "[%s:%s] %s: %s, %s" % (
                        darkgreen(repository),
                        darkred(unicode(identifier)),
                        blue(_("UGC error")),
                        doc_data,
                        err_msg,
                    )
                )
                continue
            doc_data = doc_data[0]
            data, err_msg = Equo.UGC.remove_document_autosense(repository, identifier, doc_data['iddoctype'])
            if data == False:
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

def showDocument(mydict, repository, pkgkey):

    title = unicode(mydict['title'],'raw_unicode_escape')
    if not title: title = _("No title")
    title = darkgreen(title)
    doctype = None
    for item in etpConst['ugc_doctypes']:
        if etpConst['ugc_doctypes'][item] == mydict['iddoctype']:
            doctype = item
            break
    if doctype == None: doctype = _("Unknown type")
    print_info(" %s [%s|%s|%s|%s|%s|%s]" % (
            bold(u"@@"),
            bold(unicode(mydict['iddoc'])),
            darkred(unicode(doctype)),
            darkgreen(unicode(repository)),
            purple(unicode(pkgkey)),
            blue(unicode(mydict['username'])),
            darkgreen(unicode(mydict['ts'])),
        )
    )
    print_info("\t%s: %s" % (
            blue(_("Title")),
            title,
        )
    )
    text = mydict['ddata'].tostring()
    text = unicode(text,'raw_unicode_escape')
    _my_formatted_print(text,"\t%s: " % (blue(_("Content")),),"\t")

    print_info("\t%s: %s" % (
            blue(_("Keywords")),
            ', '.join(mydict['keywords']),
        )
    )
    print_info("\t%s: %s" % (
            blue(_("Size")),
            Equo.entropyTools.bytesIntoHuman(mydict['size']),
        )
    )
    if mydict.has_key('store_url'):
        if mydict['store_url'] != None:
            print_info("\t%s: %s" % (
                    blue(_("Download")),
                    mydict['store_url'],
                )
            )

def showVote(vote, repository, pkgkey):
    print_info(" %s [%s|%s] %s: %s" % (
            bold(u"@@"),
            darkgreen(unicode(repository)),
            purple(unicode(pkgkey)),
            darkred(_("Current package vote")),
            darkgreen(str(vote)),
        )
    )


def _my_formatted_print(data,header,reset_columns, min_chars = 25, color = None):
    if type(data) is set:
        mydata = list(data)
    elif type(data) is not list:
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
    if fcount > 0: print_info(desc_text)
